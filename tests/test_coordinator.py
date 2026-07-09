"""Coordinator behavior tests with a fake client (no network)."""

import asyncio
from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modbus_connect.client import ReadError
from custom_components.modbus_connect.const import (
    CONF_FILENAME,
    CONF_SLAVE_ID,
    DOMAIN,
    OPTION_ENABLED_GROUPS,
)
from custom_components.modbus_connect.coordinator import (
    ModbusConnectCoordinator,
    is_group_visible,
    resolve_enabled_groups,
)
from custom_components.modbus_connect.models import DeviceDef, EntityDef, Span, TemplateDef


class FakeTime:
    """Controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now


class FakeClient:
    """Duck-typed ModbusBlockClient recording every read."""

    host = "127.0.0.1"
    port = 502

    def __init__(self, registers: dict[int, int] | None = None) -> None:
        self.lock = asyncio.Lock()
        self.registers = registers or {}
        self.reads: list[Span] = []
        self.written: list[tuple[int, list[int]]] = []
        self.write_multiple_flags: list[bool] = []
        self.fail_spans: set[Span] = set()
        self.fail_addresses: set[int] = set()
        self.connected_ok = True

    async def ensure_connected(self) -> bool:
        return self.connected_ok

    async def read_block(self, device_id: int, span: Span) -> list[int]:
        self.reads.append(span)
        if span in self.fail_spans or any(
            span.start <= a < span.end for a in self.fail_addresses
        ):
            raise ReadError(f"fail {span}", illegal_address=True)
        return [self.registers.get(a, 0) for a in range(span.start, span.end)]

    async def write_registers(
        self, device_id: int, address: int, words: list[int], *, multiple: bool = False
    ) -> None:
        self.written.append((address, words))
        self.write_multiple_flags.append(multiple)
        for i, w in enumerate(words):
            self.registers[address + i] = w

    async def write_coil(self, device_id: int, address: int, value: bool) -> None:
        self.written.append((address, [int(value)]))


def make_device(
    *entities: EntityDef, max_read: int = 100, max_gap: int = 8, **kwargs: Any
) -> DeviceDef:
    return DeviceDef(
        manufacturer="Acme",
        model="X1",
        entities=entities,
        max_read=max_read,
        max_gap=max_gap,
        filename="test.yaml",
        **kwargs,
    )


def sensor(key: str, address: int, **kwargs: Any) -> EntityDef:
    kwargs.setdefault("platform", "sensor")
    return EntityDef(key=key, address=address, **kwargs)


async def make_coordinator(
    hass, device: DeviceDef, client: FakeClient, monkeypatch, faketime, options=None
):
    monkeypatch.setattr("custom_components.modbus_connect.coordinator.time", faketime)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 502, CONF_SLAVE_ID: 1, CONF_FILENAME: "test.yaml"},
        options=options or {},
    )
    entry.add_to_hass(hass)
    return ModbusConnectCoordinator(hass, entry, client, device)


async def test_adjacent_entities_one_read(hass, monkeypatch):
    client = FakeClient({0: 100, 1: 200, 2: 300})
    device = make_device(sensor("a", 0), sensor("b", 1), sensor("c", 2))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert client.reads == [Span("holding", 0, 3)]
    assert coordinator.data == {"a": 100, "b": 200, "c": 300}


async def test_device_info_shows_connection(hass, monkeypatch):
    """host:port and the Modbus id are surfaced via model_id."""
    client = FakeClient({0: 1})
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    info = coordinator.device_info
    assert info["model"] == "X1"
    assert info["model_id"] == "127.0.0.1:502 · ID 1"


async def test_scan_interval_buckets(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 1, 50: 2})
    device = make_device(sensor("fast", 0), sensor("slow", 50, scan_interval=300))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)

    await coordinator.async_refresh()  # both due initially
    assert len(client.reads) == 2  # gap of 49 > max_gap: two blocks

    client.reads.clear()
    faketime.now += 60  # only "fast" (30 s default) is due
    await coordinator.async_refresh()
    assert client.reads == [Span("holding", 0, 1)]
    assert coordinator.data["slow"] == 2  # kept from previous cycle


async def test_last_read_count_reports_block_merge(hass, monkeypatch):
    # three adjacent registers merge into a single block -> one read covers three entities
    client = FakeClient({0: 1, 1: 2, 2: 3})
    device = make_device(sensor("a", 0), sensor("b", 1), sensor("c", 2))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.last_read_count == 1  # one block covered all three
    assert coordinator.last_polled_count == 3
    assert coordinator.read_entity_count == 3
    assert len(client.reads) == 1  # a single Modbus transaction


async def test_last_read_count_counts_separate_blocks(hass, monkeypatch):
    # a gap wider than max_gap forces two separate reads
    client = FakeClient({0: 1, 100: 2})
    device = make_device(sensor("a", 0), sensor("b", 100), max_gap=8)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.last_read_count == 2
    assert coordinator.last_polled_count == 2
    assert len(client.reads) == 2


async def test_last_polled_count_tracks_due_subset(hass, monkeypatch):
    # when only the fast entity is due, both counts drop to that subset
    faketime = FakeTime()
    client = FakeClient({0: 1, 50: 2})
    device = make_device(sensor("fast", 0), sensor("slow", 50, scan_interval=300))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
    await coordinator.async_refresh()  # both due
    assert coordinator.last_polled_count == 2
    assert coordinator.last_read_count == 2  # gap > max_gap -> two blocks

    faketime.now += 60  # only "fast" is due now
    await coordinator.async_refresh()
    assert coordinator.last_polled_count == 1
    assert coordinator.last_read_count == 1
    assert coordinator.read_entity_count == 2  # total is constant


async def test_read_count_sensor_reports_stable_full_refresh(hass, monkeypatch):
    from homeassistant.const import EntityCategory

    from custom_components.modbus_connect.sensor import ModbusConnectReadCountSensor

    faketime = FakeTime()
    client = FakeClient({0: 1, 1: 2, 50: 3})
    # two adjacent fast entities (one merged block) + a distant slow one (a second)
    device = make_device(
        sensor("a", 0), sensor("b", 1), sensor("slow", 50, scan_interval=300)
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
    await coordinator.async_refresh()  # all due -> two blocks

    entity = ModbusConnectReadCountSensor(coordinator)
    assert entity.native_value == 2  # full refresh: a+b in one block, slow in another
    assert entity.extra_state_attributes == {"read_entities": 3}
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.unique_id.endswith("_reads_per_refresh")
    # diagnostic gauge -> no long-term statistics
    assert entity.state_class is None

    # a partial cycle (only the fast block due) leaves the reported figure put,
    # so it does not churn the recorder even though fewer reads actually happened
    faketime.now += 60
    await coordinator.async_refresh()
    assert coordinator.last_read_count == 1  # only the fast block was issued
    assert entity.native_value == 2  # ...but the full-refresh figure is unchanged


# --- entity groups -----------------------------------------------------------


def test_is_group_visible_untagged_always_shown():
    assert is_group_visible((), frozenset({"basic"})) is True  # no groups -> always
    assert is_group_visible((), frozenset()) is True
    assert is_group_visible(("basic",), frozenset({"basic"})) is True
    assert is_group_visible(("advanced",), frozenset({"basic"})) is False
    assert is_group_visible(("basic", "all"), frozenset({"all"})) is True


def test_resolve_enabled_groups_precedence():
    dev = make_device(sensor("a", 0, groups=("basic", "all")), default_groups=("basic",))
    # option wins
    assert resolve_enabled_groups(dev, {OPTION_ENABLED_GROUPS: ["all"]}) == frozenset({"all"})
    # else the device default
    assert resolve_enabled_groups(dev, None) == frozenset({"basic"})
    assert resolve_enabled_groups(dev, {}) == frozenset({"basic"})
    # no default set -> every declared group (shows everything)
    dev2 = make_device(sensor("a", 0, groups=("x", "y")))
    assert resolve_enabled_groups(dev2, None) == frozenset({"x", "y"})
    # no groups at all -> empty (feature inactive; every entity is untagged anyway)
    dev3 = make_device(sensor("a", 0))
    assert resolve_enabled_groups(dev3, None) == frozenset()


async def test_groups_hide_and_prune_hidden_reads(hass, monkeypatch):
    client = FakeClient({0: 1, 2: 3, 100: 2})
    device = make_device(
        sensor("core", 0, groups=("basic", "all")),
        sensor("untagged", 2),  # no groups -> always visible
        sensor("extra", 100, groups=("advanced", "all")),  # hidden under basic
        default_groups=("basic",),
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    assert coordinator.enabled_groups == frozenset({"basic"})
    assert coordinator.all_groups == ("basic", "all", "advanced")  # first-seen order
    assert {e.key for e in coordinator.visible_entities} == {"core", "untagged"}
    assert coordinator.read_entity_count == 2  # 'extra' is not polled

    await coordinator.async_refresh()
    assert set(coordinator.data) == {"core", "untagged"}
    read_addrs = {a for span in client.reads for a in range(span.start, span.end)}
    assert 100 not in read_addrs  # the advanced-only block is pruned entirely


async def test_enabling_group_via_option_shows_and_reads(hass, monkeypatch):
    client = FakeClient({0: 1, 100: 2})
    device = make_device(
        sensor("core", 0, groups=("basic", "all")),
        sensor("extra", 100, groups=("advanced", "all")),
        default_groups=("basic",),
    )
    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={OPTION_ENABLED_GROUPS: ["basic", "advanced"]},
    )
    assert {e.key for e in coordinator.visible_entities} == {"core", "extra"}
    await coordinator.async_refresh()
    read_addrs = {a for span in client.reads for a in range(span.start, span.end)}
    assert 100 in read_addrs
    assert coordinator.data == {"core": 1, "extra": 2}


async def test_group_closure_keeps_hidden_template_source_polled(hass, monkeypatch):
    # A basic template reads a sensor that is itself advanced-only (hidden). The
    # closure must keep that source register polled even though its entity is gone.
    client = FakeClient({0: 5})
    device = make_device(
        sensor("measured_power", 0, groups=("advanced", "all")),
        default_groups=("basic",),
        templates=(
            TemplateDef(
                key="grid_import",
                platform="sensor",
                ha={"name": "Grid import"},
                config={"state": "{{ [-(measured_power or 0), 0] | max }}"},
                groups=("basic", "all"),
            ),
        ),
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    assert {t.key for t in coordinator.visible_templates} == {"grid_import"}
    assert coordinator.visible_entities == ()  # measured_power is hidden
    assert "measured_power" in {e.key for e in coordinator._readers}  # kept by closure

    await coordinator.async_refresh()
    assert coordinator.data["measured_power"] == 5  # polled despite being hidden


async def test_group_closure_keeps_device_info_source_polled(hass, monkeypatch):
    # sw_version templates an advanced-only internal register; device-info always
    # renders, so the seed must keep that register in the read plan under basic.
    client = FakeClient({0: 1, 10: 42})
    device = make_device(
        sensor("core", 0, groups=("basic", "all")),
        EntityDef(key="fw", platform="internal", address=10, groups=("advanced", "all")),
        default_groups=("basic",),
        sw_version="{{ fw }}",
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    assert "fw" in {e.key for e in coordinator._readers}

    await coordinator.async_refresh()
    coordinator.apply_device_info()
    assert coordinator.device_info["sw_version"] == "42"


async def test_hidden_fast_entity_does_not_speed_up_tick(hass, monkeypatch):
    client = FakeClient({0: 1, 100: 2})
    device = make_device(
        sensor("slow", 0, groups=("basic", "all"), scan_interval=300),
        sensor("fast", 100, groups=("advanced", "all"), scan_interval=5),
        default_groups=("basic",),
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    # 'fast' is hidden under basic, so its 5 s cadence must not drive the tick
    assert [e.key for e in coordinator._readers] == ["slow"]
    assert coordinator._tick == 300


async def test_min_scan_interval_clamps_intervals(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2})
    # a fast cadence (5 s), but the device declares a 60 s floor
    device = make_device(
        sensor("a", 0),
        sensor("b", 1, scan_interval=5),
        scan_interval=5,
        min_scan_interval=60,
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    assert coordinator._interval_for == {"a": 60, "b": 60}
    assert coordinator.update_interval.total_seconds() == 60


async def test_scan_interval_defaults_to_30_when_nothing_set(hass, monkeypatch):
    client = FakeClient({0: 1})
    device = make_device(sensor("a", 0))  # no scan_interval, no min_scan_interval
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    assert coordinator._interval_for == {"a": 30}


async def test_min_scan_interval_is_only_a_floor(hass, monkeypatch):
    client = FakeClient({0: 1})
    # a min below the 30 s default cadence changes nothing (min never sets the cadence)
    device = make_device(sensor("a", 0), min_scan_interval=10)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    assert coordinator._interval_for == {"a": 30}


async def test_scan_interval_below_30_is_honored(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2})
    # an explicit sub-30 scan_interval is respected; an unset min imposes no floor
    device = make_device(sensor("a", 0, scan_interval=5), sensor("b", 1), scan_interval=15)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    assert coordinator._interval_for == {"a": 5, "b": 15}


async def test_user_option_raises_floor(hass, monkeypatch):
    client = FakeClient({0: 1})
    device = make_device(sensor("a", 0), scan_interval=30)
    coordinator = await make_coordinator(
        hass, device, client, monkeypatch, FakeTime(),
        options={"min_scan_interval": 120},
    )
    assert coordinator._interval_for == {"a": 120}


async def test_bad_addresses_seed_holes(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2, 6: 3, 7: 4})
    device = make_device(
        sensor("a", 0, type="uint32", count=2),
        sensor("b", 6, type="uint32", count=2),
        bad_addresses={("holding", 3)},
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    # the gap 2..6 is within max_gap, but declared-bad address 3 stops the bridge
    assert client.reads == [Span("holding", 0, 2), Span("holding", 6, 2)]
    assert coordinator.data["a"] is not None
    assert coordinator.data["b"] is not None


async def test_split_before_forces_new_block(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2, 4: 3, 5: 4})
    device = make_device(
        sensor("a", 0),
        sensor("b", 1),
        sensor("c", 4),
        sensor("d", 5),
        boundaries={("holding", 4)},
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    # without the boundary the gap 2..4 would bridge into one block
    assert client.reads == [Span("holding", 0, 2), Span("holding", 4, 2)]


async def test_bridged_hole_learned(hass, monkeypatch):
    client = FakeClient({0: 1, 1: 2, 6: 3, 7: 4})
    client.fail_addresses = {3}  # device rejects reading address 3
    device = make_device(sensor("a", 0, type="uint32", count=2), sensor("b", 6, type="uint32", count=2))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    # the bridged block failed, then both entities recovered individually
    assert client.reads == [
        Span("holding", 0, 8),  # bridged read, rejected by the device
        Span("holding", 0, 2),  # unbridged fallback reads
        Span("holding", 6, 2),
    ]
    assert coordinator._holes == {("holding", a) for a in (2, 3, 4, 5)}

    client.reads.clear()
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()
    # planner now avoids the bridge entirely
    assert client.reads == [Span("holding", 0, 2), Span("holding", 6, 2)]


async def test_partial_failure_keeps_other_entities(hass, monkeypatch):
    client = FakeClient({0: 7})
    client.fail_addresses = {50}
    device = make_device(sensor("ok", 0), sensor("broken", 50))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["ok"] == 7
    assert coordinator.data["broken"] is None  # entity unavailable, device alive


async def test_backoff_on_total_failure(hass, monkeypatch):
    client = FakeClient()
    client.connected_ok = False
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    base = coordinator.update_interval.total_seconds()

    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    first = coordinator.update_interval.total_seconds()
    await coordinator.async_refresh()
    second = coordinator.update_interval.total_seconds()
    assert first > base
    assert second > first

    client.connected_ok = True
    coordinator._next_due = dict.fromkeys(coordinator._next_due, 0.0)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.update_interval.total_seconds() == pytest.approx(base)


async def test_max_change_and_never_resets(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 100, 1: 500})
    device = make_device(
        sensor("spiky", 0, max_change=10),
        sensor("total", 1, never_resets=True),
    )
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)

    await coordinator.async_refresh()
    assert coordinator.data == {"spiky": 100, "total": 500}

    client.registers[0] = 900  # spike
    client.registers[1] = 3  # counter reset glitch
    faketime.now += 60
    await coordinator.async_refresh()
    assert coordinator.data == {"spiky": 100, "total": 500}

    client.registers[0] = 105  # sane change
    faketime.now += 60
    await coordinator.async_refresh()
    assert coordinator.data["spiky"] == 105


async def test_write_encodes_and_confirms(hass, monkeypatch):
    client = FakeClient({0: 150})
    defn = EntityDef(
        key="setpoint",
        platform="number",
        address=0,
        multiplier=0.1,
        ha={"native_min_value": 0, "native_max_value": 50},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()
    assert coordinator.data["setpoint"] == 15

    await coordinator.async_write(defn, 21.5)
    assert client.written == [(0, [215])]
    assert coordinator.data["setpoint"] == pytest.approx(21.5)  # confirmed by read-back


async def test_masked_write_read_modify_write(hass, monkeypatch):
    client = FakeClient({0: 0x0A5F})
    defn = EntityDef(
        key="nibble",
        platform="number",
        address=0,
        mask=0x00F0,
        read_modify_write=True,
        ha={"native_min_value": 0, "native_max_value": 15},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()

    await coordinator.async_write(defn, 3)
    assert client.written == [(0, [0x0A3F])]  # other bits preserved


async def test_read_register_reads_linked_value_and_writes_own(hass, monkeypatch):
    # 'charge_current' is shown from reg 144 (via a readback entity) but written to reg 36
    client = FakeClient({144: 250, 36: 0})
    readback = EntityDef(key="cc_readback", platform="internal", address=144, multiplier=0.1)
    defn = EntityDef(
        key="charge_current", platform="number", address=36, multiplier=0.1,
        read_register="{{ cc_readback }}", ha={"native_min_value": 0, "native_max_value": 50},
    )
    coordinator = await make_coordinator(
        hass, make_device(readback, defn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()
    assert coordinator.data["charge_current"] == pytest.approx(25.0)  # from reg 144 via readback
    await coordinator.async_write(defn, 30.0)
    assert client.written == [(36, [300])]  # written to its own register, not the read register
    assert coordinator.data["charge_current"] == pytest.approx(30.0)  # optimistic update


async def test_read_register_packed_read_full_write(hass, monkeypatch):
    # a byte-packed read (low byte of reg 150) with a full-register write to reg 103
    client = FakeClient({150: (30 << 8) | 25, 103: 0})
    readback = EntityDef(key="soc_readback", platform="internal", address=150, mask=0x00FF)
    defn = EntityDef(
        key="min_soc", platform="number", address=103, read_register="{{ soc_readback }}",
        ha={"native_min_value": 0, "native_max_value": 100},
    )
    coordinator = await make_coordinator(
        hass, make_device(readback, defn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()
    assert coordinator.data["min_soc"] == 25  # low byte of reg 150 via the readback entity
    await coordinator.async_write(defn, 40)
    assert client.written == [(103, [40])]  # full value written to reg 103


async def test_static_value_entity_never_reads_and_writes_fc16(hass, monkeypatch):
    # a write-only command register: shown from static_value, never read, written via FC16
    client = FakeClient({})
    defn = EntityDef(
        key="power_control", platform="select", address=124,
        value_map={0: "Disabled", 1: "Enabled"},
        static_value="Disabled", write_multiple=True, ha={},
    )
    coordinator = await make_coordinator(
        hass, make_device(defn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()
    assert coordinator.data["power_control"] == "Disabled"  # seeded value
    assert client.reads == []  # its register is never read
    await coordinator.async_write(defn, "Enabled")
    assert client.written == [(124, [1])]  # encoded through the map
    assert client.write_multiple_flags == [True]  # forced FC16
    assert coordinator.data["power_control"] == "Enabled"  # optimistic update


async def test_button_list_write_value_writes_consecutive_fc16(hass, monkeypatch):
    client = FakeClient()
    btn = EntityDef(
        key="sync", platform="button", table="holding", address=10,
        write_value=(1, "{{ 2 + 3 }}", "{{ -300 }}"), ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    await coordinator.async_write(btn, btn.write_value)
    # number, rendered template, and a negative (two's-complement) -> consecutive words
    assert client.written == [(10, [1, 5, 65236])]
    assert client.write_multiple_flags == [True]  # FC16


async def test_button_list_write_value_renders_over_current_values(hass, monkeypatch):
    client = FakeClient({0: 7})
    src = sensor("src", 0)
    btn = EntityDef(
        key="echo", platform="button", table="holding", address=20,
        write_value=("{{ src }}", "{{ src * 2 }}"), ha={},
    )
    coordinator = await make_coordinator(
        hass, make_device(src, btn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()  # decode src -> 7
    await coordinator.async_write(btn, btn.write_value)
    assert client.written == [(20, [7, 14])]  # refresh reads only; the write is the sole entry


async def test_button_list_write_value_non_numeric_raises(hass, monkeypatch):
    from homeassistant.exceptions import HomeAssistantError

    client = FakeClient()
    btn = EntityDef(
        key="bad", platform="button", table="holding", address=0,
        write_value=("{{ 'x' }}",), ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write(btn, btn.write_value)
    assert client.written == []  # nothing written when a value can't render


async def test_button_single_template_write_value_through_codec(hass, monkeypatch):
    client = FakeClient()
    btn = EntityDef(
        key="set_hour", platform="button", table="holding", address=5,
        write_value="{{ 3 + 4 }}", ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    await coordinator.async_write(btn, btn.write_value)
    assert client.written == [(5, [7])]
    assert client.write_multiple_flags == [False]  # single register -> FC06


async def test_button_single_template_respects_type(hass, monkeypatch):
    client = FakeClient()
    btn = EntityDef(
        key="big", platform="button", table="holding", address=0,
        type="int32", count=2, write_value="{{ 70000 }}", ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    await coordinator.async_write(btn, btn.write_value)
    assert client.written == [(0, [1, 4464])]  # 70000 spans two registers via the codec


async def test_button_single_template_render_failure_raises(hass, monkeypatch):
    from homeassistant.exceptions import HomeAssistantError

    client = FakeClient()
    btn = EntityDef(
        key="x", platform="button", table="holding", address=0,
        write_value="{{ 1 / 0 }}", ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    with pytest.raises(HomeAssistantError):
        await coordinator.async_write(btn, btn.write_value)
    assert client.written == []


async def test_rtc_local_template_renders_to_valid_registers(hass, monkeypatch):
    # the exact templates the SolaX converter emits for the hybrid's Sync RTC button
    client = FakeClient()
    btn = EntityDef(
        key="sync_rtc", platform="button", table="holding", address=0,
        write_value=(
            "{{ now().second }}", "{{ now().minute }}", "{{ now().hour }}",
            "{{ now().day }}", "{{ now().month }}", "{{ now().year % 100 }}",
        ), ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    await coordinator.async_write(btn, btn.write_value)
    [(addr, words)] = client.written  # exactly one write; unpack without indexing
    assert addr == 0 and len(words) == 6
    sec, minute, hour, day, month, yy = words
    assert 0 <= sec < 60 and 0 <= minute < 60 and 0 <= hour < 24
    assert 1 <= day <= 31 and 1 <= month <= 12 and 0 <= yy < 100


async def test_rtc_utc_tz_template_renders_to_valid_registers(hass, monkeypatch):
    # the EV-charger form: UTC offset (two's-complement minutes) followed by UTC time
    client = FakeClient()
    btn = EntityDef(
        key="sync_rtc", platform="button", table="holding", address=0x61D,
        write_value=(
            "{{ ((now().utcoffset().total_seconds() // 60) | int) % 65536 }}",
            "{{ utcnow().second }}", "{{ utcnow().minute }}", "{{ utcnow().hour }}",
            "{{ utcnow().day }}", "{{ utcnow().month }}", "{{ utcnow().year % 100 }}",
        ), ha={},
    )
    coordinator = await make_coordinator(hass, make_device(btn), client, monkeypatch, FakeTime())
    await coordinator.async_write(btn, btn.write_value)
    [(addr, words)] = client.written  # exactly one write; unpack without indexing
    assert addr == 0x61D and len(words) == 7
    assert all(0 <= w <= 0xFFFF for w in words)  # tz offset wraps into a valid uint16


async def test_optimistic_default_reads_with_fallback(hass, monkeypatch):
    # optimistic_default DOES read the register, but an undecodable value falls back
    # to the default so the control stays usable
    defn = EntityDef(
        key="mode", platform="select", address=50,
        value_map={0: "Off", 1: "On"}, optimistic_default="Off", ha={},
    )
    bad = await make_coordinator(hass, make_device(defn), FakeClient({50: 99}), monkeypatch, FakeTime())
    await bad.async_refresh()
    assert bad.client.reads  # unlike static_value, the register is read
    assert bad.data["mode"] == "Off"  # 99 is not in the map -> fallback

    good = await make_coordinator(hass, make_device(defn), FakeClient({50: 1}), monkeypatch, FakeTime())
    await good.async_refresh()
    assert good.data["mode"] == "On"  # a decodable value is shown as itself


async def test_time_entity_reads_and_writes(hass, monkeypatch):
    from datetime import time

    client = FakeClient({104: 3102})  # 12:30 packed as 12*256 + 30
    defn = EntityDef(key="charge_start", platform="time", address=104, type="time", ha={})
    coordinator = await make_coordinator(
        hass, make_device(defn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()
    assert coordinator.data["charge_start"] == time(12, 30)
    await coordinator.async_write(defn, time(6, 15))
    assert client.written == [(104, [(6 << 8) | 15])]  # 6*256 + 15
    assert coordinator.data["charge_start"] == time(6, 15)  # confirmed by read-back


async def test_two_register_time_reads_and_writes(hass, monkeypatch):
    from datetime import time

    # SolaX EV charger form: hour at 0x634, minute at 0x635
    client = FakeClient({0x634: 12, 0x635: 30})
    defn = EntityDef(
        key="boost_start", platform="time", address=0x634, type="time", count=2, ha={}
    )
    coordinator = await make_coordinator(
        hass, make_device(defn), client, monkeypatch, FakeTime()
    )
    await coordinator.async_refresh()
    assert coordinator.data["boost_start"] == time(12, 30)
    assert client.reads == [Span("holding", 0x634, 2)]  # both registers, one block
    await coordinator.async_write(defn, time(6, 15))
    assert client.written == [(0x634, [6, 15])]  # hour then minute, consecutive registers
    assert coordinator.data["boost_start"] == time(6, 15)  # confirmed by read-back


async def test_nothing_due_returns_cache(hass, monkeypatch):
    faketime = FakeTime()
    client = FakeClient({0: 5})
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, faketime)
    await coordinator.async_refresh()
    client.reads.clear()

    await coordinator.async_refresh()  # nothing due yet
    assert client.reads == []
    assert coordinator.data == {"a": 5}


async def test_all_reads_fail_raises(hass, monkeypatch):
    client = FakeClient()
    client.fail_addresses = {0}
    device = make_device(sensor("a", 0))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_partial_fallback_learns_no_holes(hass, monkeypatch):
    client = FakeClient({0: 1, 6: 2})
    client.fail_addresses = {6}  # a real entity address fails, not a bridge
    device = make_device(sensor("a", 0), sensor("b", 6))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data == {"a": 1, "b": None}
    assert coordinator._holes == set()


async def test_write_cannot_connect_raises(hass, monkeypatch):
    from homeassistant.exceptions import HomeAssistantError

    client = FakeClient({0: 1})
    defn = EntityDef(
        key="x",
        platform="number",
        address=0,
        ha={"native_min_value": 0, "native_max_value": 10},
    )
    device = make_device(defn)
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())
    await coordinator.async_refresh()

    client.connected_ok = False
    with pytest.raises(HomeAssistantError, match="Cannot connect"):
        await coordinator.async_write(defn, 5)


async def test_undecodable_value_becomes_none(hass, monkeypatch):
    client = FakeClient({0: 1})
    # count contradicts the type width; decode raises and the value is None
    device = make_device(sensor("broken", 0, type="float32", count=1))
    coordinator = await make_coordinator(hass, device, client, monkeypatch, FakeTime())

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["broken"] is None
