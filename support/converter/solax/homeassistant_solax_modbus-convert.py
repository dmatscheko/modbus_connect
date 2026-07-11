#!/usr/bin/env python3
"""Convert homeassistant-solax-modbus plugin entity descriptions -> modbus_connect YAML.

Unlike ``modbus_local_gateway-convert.py`` this is NOT standalone: it imports the
upstream SolaX plugin modules, so it needs Home Assistant installed and a checkout of
https://github.com/wills106/homeassistant-solax-modbus. It filters the entity
descriptions to a target inverter spec (bitmask) and Modbus protocol document version
(modbus_min/modbus_max) and emits our declarative device-config format, skipping
computed/local entities (no real register, value_function, callable scale,
write_method=local) and reporting what it dropped. Settings that echo on a different
register than they are written to (selects, numbers, and the gen4time mirrors of the
time entities) read through a linked ``_readback`` entity, so write-only command
registers are never polled; single-write registers with no read-back at all become
seeded ``static_value`` controls. Regenerates the bundled Solax_X3_Hybrid_G4.yaml and
Solax_X3_HAC.yaml.

Usage (point SOLAX_MODBUS_REPO at your checkout, else the default path is used):

    SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \\
        python3 converter/homeassistant_solax_modbus-convert.py
"""
import importlib
import importlib.util
import os
import sys
import types
from collections import Counter
from pathlib import Path

# The shared augment library — the single writer of every bundled device config.
_COMMON = Path(__file__).resolve().parents[1] / "_common"
_aug_spec = importlib.util.spec_from_file_location("augment", _COMMON / "augment.py")
augment = importlib.util.module_from_spec(_aug_spec)
_aug_spec.loader.exec_module(augment)

# Checkout of the upstream homeassistant-solax-modbus repo to read entity descriptions from.
ROOT = os.environ.get(
    "SOLAX_MODBUS_REPO",
    "/Users/dma/Eigenes/Development/home_assistant_projects/homeassistant-solax-modbus",
)


def load_plugin(modname):
    for name, sub in (("custom_components", ""), ("custom_components.solax_modbus", "/solax_modbus")):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [ROOT + "/custom_components" + sub]
            sys.modules[name] = m
    return importlib.import_module(f"custom_components.solax_modbus.{modname}")


def enum_str(v):
    return getattr(v, "value", v)


# Scan timing. SolaX sorts registers into scan groups: live values (power/current/
# voltage on input registers) poll FAST, while slow-changing ones (energy, temperature,
# frequency) and all settings (holding) poll MEDIUM. We map FAST -> 15 s and let
# everything else inherit the device default (30 s). This follows SolaX's AUTO rule
# (default_input_scangroup on the hybrid) and applies it uniformly to the EV charger
# too, whose live values would otherwise inherit its slower default group.
FAST_INTERVAL = 15
# Units SolaX treats as slow-changing (auto_slow_scangroup); everything else is fast.
SLOW_UNITS = {"Wh", "kWh", "Hz", "°C", "°F", "K", "h"}


def fast_tier(e):
    """True if this is a live input-register value SolaX polls in its FAST group, so it
    gets the fast scan_interval. Holding registers, slow-changing units, and entities
    explicitly tagged DEFAULT/MEDIUM inherit the slower device default instead."""
    group = enum_str(getattr(e, "scan_group", None)) or ""
    if group == "scan_interval_fast":
        return True
    if group in ("scan_interval", "scan_interval_medium"):  # explicit DEFAULT / MEDIUM
        return False
    if getattr(e, "register_type", None) != 2:  # REG_INPUT; holding/other -> not fast
        return False
    return enum_str(getattr(e, "native_unit_of_measurement", None)) not in SLOW_UNITS


# solax register_data_type -> (our type | None for uint16 default, is-32bit, mask)
DTYPE = {
    "_uint16": (None, False, None),
    "_int16": ("int16", False, None),
    "_uint32": ("uint32", True, None),
    "_int32": ("int32", True, None),
    "_float32": ("float32", True, None),
    "_ulsb16msb16": ("uint32", True, None),
    "_int8L": (None, False, 0x00FF),
    "_int8H": (None, False, 0xFF00),
    "_string": ("string", False, None),
}
WRITE_LOCAL = 3
# write_method 2 (MULTISINGLE) and 4 (MULTI) both use FC16. Registers written this
# way are "direct" command registers with no read-back — write-only in our terms.
WRITE_FC16 = (2, 4)

# SolaX reads a setting's current time through an internal sensor whose `scale`
# is one of these callables; each maps to the equivalent fields of our `time`
# type (our packed form is hour-high/minute-low, so gen4's minute-high mirrors
# need a byte swap). rectify_time keeps SolaX's 24:00 end-of-day readable.
TIME_SCALE_FIELDS = {
    "value_function_gen4time": {"type": "time", "swap": "byte", "rectify_time": True},
    "value_function_sofartime": {"type": "time", "rectify_time": True},
    "value_function_gen23time": {"type": "time", "count": 2, "rectify_time": True},
    "value_function_separate_registers_time": {"type": "time", "count": 2, "rectify_time": True},
}


def make_static(e, b, ha, option_map, multiple=True):
    """A write-only command register: never read, always shows the seeded value
    (from initvalue) and off by default (advanced/expert direct-control registers).
    The presence of static_value marks the entity write-only; FC16 registers also
    set write_multiple."""
    if multiple:
        b["write_multiple"] = True
    iv = getattr(e, "initvalue", None)
    if option_map is not None:  # select: seed is an option label
        b["static_value"] = str(option_map.get(iv, next(iter(option_map.values()))))
    else:  # number: seed is the numeric initvalue (0 if unset)
        b["static_value"] = iv if iv is not None else 0
    ha["enabled_by_default"] = False


def ha_common(e, platform):
    ha = {"platform": platform}
    name = getattr(e, "name", None)
    if isinstance(name, str) and name:
        ha["name"] = name
    dc = getattr(e, "device_class", None)
    if dc is not None:
        ha["device_class"] = enum_str(dc)
    sc = getattr(e, "state_class", None)
    if sc is not None:
        ha["state_class"] = enum_str(sc)
    unit = getattr(e, "native_unit_of_measurement", None)
    if unit is not None:
        ha["unit_of_measurement"] = enum_str(unit)
    icon = getattr(e, "icon", None)
    if icon:
        ha["icon"] = icon
    ec = getattr(e, "entity_category", None)
    if ec is not None:
        ha["entity_category"] = enum_str(ec)
    if getattr(e, "entity_registry_enabled_default", True) is False:
        ha["enabled_by_default"] = False
    sdp = getattr(e, "suggested_display_precision", None)
    if platform == "sensor" and sdp is not None:  # numbers show whole steps already
        ha["precision"] = sdp
    return ha


def table_of(e):
    return "holding" if e.register_type == 1 else "input"


def apply_scale(e, b, ha):
    """Fold SolaX's scale onto the modbus base + ha block. Returns True if the scale
    is a value_function (callable) we can't express, making this a read source only."""
    scale = getattr(e, "scale", 1)
    if callable(scale):
        if getattr(scale, "__name__", "") == "value_function_disabled_enabled":
            b["map"] = {0: "Disabled", 1: "Enabled"}  # the callable is just this map
            return False
        return True  # register-only read source; a merging writable supplies the conversion
    if isinstance(scale, dict):
        b["map"] = {int(k): str(v) for k, v in scale.items()}
        return False
    mult = float(scale) * float(getattr(e, "read_scale", 1) or 1)
    if mult != 1:
        b["multiplier"] = round(mult, 10)
    if 0 < mult < 1 and ha.get("unit_of_measurement") is not None:
        ha.setdefault("precision", getattr(e, "rounding", 1))
    return False


class _Converter:
    """Accumulates converted entities across the SolaX entity-description tables.

    SolaX gives each writable setting a read-back *sensor* and a *number/select* at
    DIFFERENT registers. We read from the sensor's register and write to the number/
    select's (address / write_address) rather than dropping either. The per-table
    handlers below share the read index and dedupe/skip bookkeeping held here; each
    handles one entity so no single one carries the whole pipeline's complexity.
    """

    def __init__(self, pi, spec, protocol=None, features=()):
        self.pi = pi
        self.spec = spec
        # Optional-feature gates: (allowedtypes bit, group name). Upstream only
        # creates these entities when the matching config checkbox is on (Parallel
        # Mode / EPS / dry contact box); we convert them all and tag each with a
        # named group so the integration's group switches give the same opt-in at
        # runtime — off by default, no registers polled until enabled.
        self.features = features
        # Modbus protocol *document* version to convert for (SolaX gates entities on
        # it via modbus_min/modbus_max, and the device reports its own on holding
        # 0x82 — the modbus_protocol_version sensor). None keeps every variant,
        # first-wins (the pre-gating behavior).
        self.protocol = protocol
        # Plugin-wide 32-bit word order; individual entities may override with
        # their own order32 (SolaX applies the same attribute to strings).
        self.order32 = enum_str(getattr(pi, "order32", None)) or "little"
        self.skipped = Counter()
        # read_of indexes convertible sensors by key, plus SolaX's `internal` read-back
        # mirrors (used to display a setting's current value) so writables can read
        # through them; those mirrors are never emitted as their own entity.
        self.read_of = {}
        self.sensor_ha = {}    # key -> ha block, for sensors emitted in their own right
        self.order = []        # emission order of those sensors
        self.consumed = set()  # read keys merged into a writable
        self.entities = []     # (table, key, base) output rows
        self.seen = set()      # emitted keys, for dedupe
        self.boundaries = set()  # (table, address) of SolaX newblock flags

    def feature_tag(self, b, e):
        """Mark the entity dict with the feature groups its allowedtypes gate on
        (consumed by annotate_groups; never emitted itself). A feature's group may
        be a plain name or a callable(key) -> [names] that splits one feature bit
        across several groups (the parallel-mode per-inverter split)."""
        groups = []
        for bit, g in self.features:
            if e.allowedtypes & bit:
                groups.extend(g(e.key) if callable(g) else [g])
        if groups:
            b["_feature"] = groups
        return b

    def match(self, e):
        if not self.pi.matchInverterWithMask(self.spec, e.allowedtypes):
            return False
        if self.protocol is not None:
            lo, hi = getattr(e, "modbus_min", None), getattr(e, "modbus_max", None)
            if (lo is not None and self.protocol < lo) or (hi is not None and self.protocol > hi):
                self.skipped["protocol-version"] += 1
                return False
        return True

    def base_fields(self, e):
        """Modbus-level fields shared by all register-backed entities. Returns None
        if unconvertible."""
        reg = getattr(e, "register", None)
        if reg is None or reg < 0:
            return None  # computed / local-only
        dtype = getattr(e, "register_data_type", None) or "_uint16"
        if dtype in ("_words",) or dtype not in DTYPE:
            return None
        typ, wide, mask = DTYPE[dtype]
        order = enum_str(getattr(e, "order32", None)) or self.order32
        if dtype == "_string" and order != "big":
            return None  # pymodbus renders little-order strings word-reversed
        if dtype == "_ulsb16msb16" and order != "little":
            return None  # the big-order variant is not a plain uint32
        out = {"address": reg}
        if typ:
            out["type"] = typ
        if dtype == "_string":
            out["count"] = getattr(e, "wordcount", None) or 1
        if wide and order == "little":
            out["swap"] = "word"
        if mask is not None:
            out["mask"] = mask
        return out

    def add(self, table, key, b):
        if key in self.seen:
            self.skipped["dupe-key"] += 1
            return
        self.seen.add(key)
        self.entities.append((table, key, b))

    def link_readback(self, key, write_table, wbase):
        """If the setting echoes on a different register than it's written to, emit
        that read-back as an internal entity and point wbase.read_register at it."""
        if key not in self.read_of:
            return  # no companion; the writable reads/writes its own register
        rtable, rbase = self.read_of[key]
        self.consumed.add(key)
        if (rtable, rbase["address"]) == (write_table, wbase["address"]):
            return  # read register == write register; nothing extra needed
        rbase = dict(rbase)
        # If the read source has no scale conversion (SolaX's value_function scales
        # are dropped, leaving just the register/mask), borrow the writable's — the
        # two ends of a setting share the same map/multiplier. A read source with
        # its OWN map keeps it: the two registers may encode the same labels with
        # different values (lock_state writes 0/2014/6868 but reads back 0/1/2).
        # Never borrow onto a source that already has the other kind: map+multiplier
        # cannot combine.
        if "map" not in rbase and "map" in wbase and "multiplier" not in rbase:
            rbase["map"] = wbase["map"]
        elif "multiplier" not in rbase and "multiplier" in wbase and "map" not in rbase:
            rbase["multiplier"] = wbase["multiplier"]
        rkey = key + "_readback"
        self.add(rtable, rkey, {**rbase, "internal": True})
        wbase["read_register"] = "{{ " + rkey + " }}"

    def _emit_writable(self, e, b, ha, omap):
        """Wire a select/number's write path (FC16 direct command -> static seed, else
        link the split read-back), attach its ha block, and add it under holding."""
        skey = getattr(e, "sensor_key", None) or e.key
        if getattr(e, "write_method", 1) in WRITE_FC16:
            make_static(e, b, ha, omap)
        elif skey not in self.read_of:
            # Nothing ever reads this register back (upstream keeps only a local
            # echo; the register may read as something else entirely, e.g. the
            # remote-control duration shares its address with the protocol-version
            # register): seed it like the FC16 direct commands, but write with FC6.
            make_static(e, b, ha, omap, multiple=False)
        else:
            # The writable's companion read-back sensor (named via sensor_key when
            # the key differs).
            self.link_readback(skey, "holding", b)
        b["ha"] = ha
        self.add("holding", e.key, b)

    def read_sensor(self, e):
        """Index one convertible sensor as a read source (the read side)."""
        if not self.match(e):
            return
        # SolaX newblock = the device fails a block read that runs into this
        # register from an earlier start; kept as a split_before boundary even
        # when the sensor itself is unconvertible.
        if getattr(e, "newblock", False):
            reg = getattr(e, "register", None)
            if isinstance(reg, int) and reg >= 0:
                self.boundaries.add((table_of(e), reg))
        if getattr(e, "value_function", None) is not None:
            self.skipped["sensor:value_function"] += 1
            return
        b = self.base_fields(e)
        if b is None:
            self.skipped["sensor:no-register"] += 1
            return
        self.feature_tag(b, e)
        ha = ha_common(e, "sensor")
        # A time-format mirror (SolaX reads a time setting's current value through
        # an internal sensor with a time-rendering scale): expressed as our `time`
        # type so the linked time entity receives a real time-of-day.
        time_fields = TIME_SCALE_FIELDS.get(
            getattr(getattr(e, "scale", None), "__name__", None)
        )
        if time_fields is not None:
            b.update(time_fields)
            read_source_only = True  # only ever a time entity's read source
        else:
            read_source_only = apply_scale(e, b, ha)
        if e.key in self.read_of:  # first wins (prefer the real register over variants)
            return
        if fast_tier(e):  # live value: poll faster than the device default
            b["scan_interval"] = FAST_INTERVAL
        self.read_of[e.key] = (table_of(e), b)
        if read_source_only or getattr(e, "internal", False):
            self.skipped["sensor:read-source-only"] += 1  # a read source, not emitted alone
        else:
            self.sensor_ha[e.key] = ha
            self.order.append(e.key)

    def add_select(self, e):
        """A select: write register + option map; read via companion if split."""
        wm = getattr(e, "write_method", 1)
        if not self.match(e) or wm == WRITE_LOCAL:
            return
        if e.key in self.seen:
            self.skipped["dupe-key"] += 1
            return
        od = getattr(e, "option_dict", None)
        if not od:
            self.skipped["select:no-options"] += 1
            return
        b = self.base_fields(e)
        if b is None:
            self.skipped["select:no-register"] += 1
            return
        self.feature_tag(b, e)
        omap = {int(k): str(v) for k, v in od.items()}
        b["map"] = omap
        self._emit_writable(e, b, ha_common(e, "select"), omap)

    def add_number(self, e):
        """A number: write register + scale; read via companion if split."""
        wm = getattr(e, "write_method", 1)
        if not self.match(e) or wm == WRITE_LOCAL:
            return
        if callable(getattr(e, "scale", 1)):
            return
        if e.key in self.seen:
            self.skipped["dupe-key"] += 1
            return
        lo, hi = getattr(e, "native_min_value", None), getattr(e, "native_max_value", None)
        if lo is None or hi is None:
            self.skipped["number:no-min-max"] += 1
            return
        b = self.base_fields(e)
        if b is None:
            self.skipped["number:no-register"] += 1
            return
        self.feature_tag(b, e)
        scale = float(getattr(e, "scale", 1) or 1)
        if scale != 1:
            b["multiplier"] = round(scale, 10)
        ha = ha_common(e, "number")
        ha["min"], ha["max"] = lo, hi
        if getattr(e, "native_step", None) is not None:
            ha["step"] = e.native_step
        self._emit_writable(e, b, ha, None)

    def add_time(self, e):
        """A time. GEN4 packs HH:MM in one register (hour*256 + minute, GEN2/3 pack
        the reverse -> ``swap: byte``); the EV charger uses two registers (hour,
        then minute) -> our ``count: 2`` form. Like selects/numbers, a time's
        current value may echo on a different register (SolaX's gen4time mirrors);
        that read-back is linked so the write register itself is never read."""
        if not self.match(e):
            return
        if e.key in self.seen:
            self.skipped["dupe-key"] += 1
            return
        reg = getattr(e, "register", None)
        if reg is None or reg < 0:
            self.skipped["time:no-register"] += 1
            return
        wordcount = getattr(e, "wordcount", None) or 1
        if wordcount not in (1, 2):
            self.skipped["time:multi-register"] += 1  # only 1- and 2-register forms handled
            return
        b = self.feature_tag({"address": reg, "type": "time"}, e)
        if wordcount == 2:  # separate registers: first = hour, second = minute
            b["count"] = 2
        else:
            # The option_dict reveals the packed write format: value 1 means 00:01
            # when the hour is in the high byte (our native form) and 01:00 when the
            # minute is (GEN2/3) — then reads and writes both need the byte swap.
            packed_1 = (getattr(e, "option_dict", None) or {}).get(1)
            if packed_1 == "01:00":
                b["swap"] = "byte"
            elif packed_1 not in (None, "00:01"):
                self.skipped["time:unknown-packing"] += 1
                return
        self.link_readback(getattr(e, "sensor_key", None) or e.key, "holding", b)
        if "read_register" not in b:
            # This entity decodes its own register; a stop time of 24:00 (end of
            # day) shows as 23:59 rather than dropping out — otherwise that slot
            # would be unavailable. (Linked read-backs carry their own rectify.)
            b["rectify_time"] = True
        b["ha"] = ha_common(e, "time")
        self.add("holding", e.key, b)

    def add_button(self, e):
        """A button: no read register; write to its own register."""
        if not self.match(e):
            return
        if getattr(e, "value_function", None) is not None or getattr(e, "command", None) is None:
            self.skipped["button:computed"] += 1
            return
        if getattr(e, "register", None) is None:
            self.skipped["button:no-register"] += 1
            return
        b = self.feature_tag(
            {"address": e.register, "write_value": e.command, "ha": ha_common(e, "button")}, e
        )
        if getattr(e, "write_method", 1) in WRITE_FC16:
            b["write_multiple"] = True
        self.add("holding", e.key, b)

    def add_remaining_sensor(self, key):
        """Emit a sensor that wasn't merged into a writable."""
        if key in self.consumed:
            return
        table, b = self.read_of[key]
        b = dict(b)
        b["ha"] = self.sensor_ha[key]
        self.add(table, key, b)

    def run(self):
        for e in self.pi.SENSOR_TYPES:
            self.read_sensor(e)
        for e in self.pi.SELECT_TYPES:
            self.add_select(e)
        for e in self.pi.NUMBER_TYPES:
            self.add_number(e)
        for e in self.pi.TIME_TYPES:
            self.add_time(e)
        for e in self.pi.BUTTON_TYPES:
            self.add_button(e)
        for key in self.order:  # remaining sensors, in discovery order
            self.add_remaining_sensor(key)
        return self.entities, self.skipped, self.boundaries


def convert(pi, spec, protocol=None, features=()):
    """Convert a plugin's entity descriptions for one inverter spec into our
    declarative entities. See :class:`_Converter` for how a setting's split
    read/write registers are recombined and what ``protocol`` and ``features``
    gate."""
    return _Converter(pi, spec, protocol, features).run()


# --- entity groups -----------------------------------------------------------
#
# Each entity/template is tagged with the tier it belongs to so the integration's
# group switches can show a subset. A hand-curated "basic" set is the minimal
# everyday view (the always-on reserved group); everything SolaX enables by
# default is "advanced". The hidden expert entities carry no tag at all — they
# belong only to the implicit "all" group, whose switch reveals every entity.
# The device defaults to showing only "basic".
#
# Entities upstream gates behind an optional-feature checkbox (Parallel Mode /
# EPS / dry contact box, see _Converter.features) skip the tiers entirely and
# carry their feature group instead — created only while that group's switch is
# on, exactly like upstream's opt-in, but toggleable at runtime.

# The keys that make up the everyday view of each device (the basic tier).
HYBRID_BASIC = frozenset({
    "run_mode", "pv_power_total", "pv_power_1", "pv_power_2",
    "pv_voltage_1", "pv_voltage_2", "inverter_power", "inverter_temperature",
    "battery_power_charge", "battery_capacity", "bdc_status",
    "today_s_solar_energy", "total_solar_energy", "total_yield",
    "battery_input_energy_today", "battery_output_energy_today",
    "inverter_voltage", "inverter_current",
    "inverter_current_l1", "inverter_current_l2", "inverter_current_l3",
    "inverter_power_l1", "inverter_power_l2", "inverter_power_l3",
    "inverter_voltage_l1", "inverter_voltage_l2", "inverter_voltage_l3",
    "device_lock",  # writable settings need the unlock reachable in basic
})
HAC_BASIC = frozenset({
    "charge_power_total", "charge_added", "charge_added_cum",
    "charge_current",
    "charge_current_l1", "charge_current_l2", "charge_current_l3",
    "charger_use_mode",
    "device_lock",  # writable settings need the unlock reachable in basic
})

# Entities promoted into an extra group on top of their tier (upstream's Energy
# Dashboard switches reveal these under new names; we show the real entity
# instead of a copy). Promotion also force-enables the entity — whoever flips
# that group's switch wants the value without an extra registry click.
HYBRID_EXTRA_GROUPS = {
    # upstream ED "Grid to Battery Energy" = the e_charge_today register
    "e_charge_today": ("grid_to_battery",),
    # A "grid" group over the inverter's per-phase grid measurements (upstream
    # ships them disabled/expert); the grid_power_* templates below derive real
    # power from them plus the hidden power-factor registers.
    **dict.fromkeys(
        (
            "grid_voltage", "grid_voltage_l1", "grid_voltage_l2", "grid_voltage_l3",
            "grid_current_total", "grid_current_l1", "grid_current_l2", "grid_current_l3",
            "grid_import", "grid_export",
        ),
        ("grid",),
    ),
}


def tier_groups(key, ha, basic):
    """The group tags for one entity/template: the curated basic set, SolaX's
    enabled-by-default entities as advanced, and no tag for the hidden expert
    entities (reachable only through the implicit all group's switch)."""
    if key in basic:
        return ["basic"]
    enabled = ha.get("enabled_by_default", True) is not False
    return ["advanced"] if enabled else []


def annotate_groups(entities, templates, basic, extra=None):
    """Attach group tags to every non-internal entity and every template in place.
    Internal read-only entities carry none (never shown; always polled when needed).
    An optional-feature entity (its ``_feature`` marker set by the converter) is in
    its feature group alone, keeping its upstream enabled/disabled default within
    it. A curated basic entity is forced enabled — SolaX ships a few of them
    disabled, but if we put one in the everyday view it should show without extra
    clicks; the same goes for an entity promoted into an ``extra`` group."""
    extra = extra or {}
    for _table, key, b in entities:
        feature = b.pop("_feature", None)
        if b.get("internal"):
            continue
        if feature:
            b["groups"] = feature
            continue
        ha = b.get("ha", {})
        promoted = extra.get(key, ())
        # Tier first (from the upstream enabled state), force-enable after — a
        # promoted expert entity joins its extra group without leaking into
        # advanced just because the promotion enables it.
        groups = [*tier_groups(key, ha, basic), *promoted]
        if key in basic or promoted:
            ha.pop("enabled_by_default", None)
        if groups:
            b["groups"] = groups
    for t in templates:
        if t.get("groups"):
            continue  # explicit tag (the PM totals carry their feature group)
        groups = tier_groups(t["key"], t.get("ha", {}), basic)
        if groups:
            t["groups"] = groups


def _to_intermediate(meta, ents, templates):
    """SolaX's converted entities + computed templates -> a tagged intermediate.

    The tier/basic/extra-group *policy* is applied from the SolaX augment.yaml; here
    the converter stamps only facts: ``internal`` and the upstream enabled-by-default
    state (so the augment.yaml's advanced fallback can tell advanced from expert). The
    structural feature groups (parallel-mode / EPS / generator) are already on the
    body from :func:`annotate_groups`."""
    ir = augment.intermediate(dict(meta))
    # SolaX emits each table sorted by address; the shared emitter preserves order.
    for table, key, body in sorted(ents, key=lambda e: e[2].get("address", 0)):
        body = dict(body)
        tags = set()
        if body.get("internal"):
            tags.add("internal")
        else:
            enabled = body.get("ha", {}).get("enabled_by_default", True) is not False
            tags.add(f"enabled-default:{'true' if enabled else 'false'}")
        augment.add_entity(ir, table, key, tags=tags, **body)
    for template in templates:
        template = dict(template)
        augment.add_entity(ir, "template", template.pop("key"), **template)
    return ir


def run(module, spec_fn, meta, filename, extras=(), templates=(), basic=frozenset(), protocol=None,
        features=None, extra_groups=None):
    P = load_plugin(module)
    ents, skipped, boundaries = convert(
        P.plugin_instance, spec_fn(P), protocol, features(P) if features else ()
    )
    ents = list(ents) + list(extras)  # device-info + computed registers, appended post-dedupe
    dupes = [k for k, n in Counter(k for _, k, _ in ents).items() if n > 1]
    if dupes:  # extras bypass the converter's dedupe; a repeat would silently last-win
        raise SystemExit(f"{filename}: duplicate entity keys {sorted(dupes)}")
    annotate_groups(ents, templates, basic, extra_groups)
    meta = dict(meta)
    note = meta.pop("note", None)
    if boundaries:
        split = {}
        for table, addr in sorted(boundaries):
            split.setdefault(table, []).append(addr)
        meta["split_before"] = split
    ir = _to_intermediate(meta, ents, templates)
    name = filename[:-5] if filename.endswith(".yaml") else filename
    augment.write_augmented(ir, name, source="homeassistant-solax-modbus", variant=__file__, note=note)
    plat = Counter(b.get("ha", {}).get("platform", "internal") for _, _, b in ents)
    print(f"\nWROTE {filename}: {dict(plat)} +{len(templates)} template total {len(ents) + len(templates)}")
    print("  skipped:", {k: v for k, v in skipped.items() if v})


def internal(table, key, **fields):
    return (table, key, {**fields, "internal": True})


def PW(name, **extra):
    """A power-sensor ha block (W, measurement); extra keys (icon, ...) are merged."""
    return {"platform": "sensor", "name": name, "device_class": "power",
            "state_class": "measurement", "unit_of_measurement": "W", **extra}


def KWH(name, **extra):
    """An energy-total ha block (kWh, total_increasing) for `integrate` templates."""
    return {"platform": "sensor", "name": name, "device_class": "energy",
            "state_class": "total_increasing", "unit_of_measurement": "kWh", **extra}


def pm_groups(key):
    """Split the parallel-mode entities into one group per inverter. The SolaX PM
    block carries inverter 1 under the plain ``pm_`` keys and inverters 2/3 under
    ``pm_i2_``/``pm_i3_``; ``pm_inverter_count`` (and the pm_total_* aggregates,
    tagged separately) belong to the whole parallel system, so they go in all
    three — a group is visible when any of its groups is enabled."""
    if key.startswith("pm_i2_"):
        return ["pm_i2"]
    if key.startswith("pm_i3_"):
        return ["pm_i3"]
    if key == "pm_inverter_count":
        return ["pm_i1", "pm_i2", "pm_i3"]
    return ["pm_i1"]


# Display labels for the per-inverter parallel-mode groups (the switch would
# otherwise show "Pm i1"); the shared PM entities live in all three.
PM_GROUP_LABELS = {
    "pm_i1": "Parallel mode Inverter 1",
    "pm_i2": "Parallel mode Inverter 2",
    "pm_i3": "Parallel mode Inverter 3",
}


def _grid_phase_power(n):
    """Real power on one grid phase: V x I x |PF|, PF the register's percent value
    (upstream labels it '%', no scale). Direction comes from the signed grid
    current; |power factor| is the 0..1 magnitude reduction, so a signed PF does
    not double the sign. `/100` and the sign are worth verifying against the Grid
    Power Factor sensor and `measured_power` on real hardware."""
    return (f"(grid_voltage_l{n} or 0) * (grid_current_l{n} or 0) "
            f"* ((grid_power_factor_l{n} or 0) | abs)")


def grid_power_templates():
    """Per-phase and total real grid power over the `grid` group's V/I sensors and
    the (hidden but still polled) power-factor registers. Templates render over
    entity values, never each other, so the total inlines the three phase
    expressions instead of summing the grid_power_l* templates."""
    phases = [
        {"key": f"grid_power_l{n}",
         "state": "{{ ((" + _grid_phase_power(n) + ") / 100) | round | int }}",
         "ha": PW(f"Grid Power L{n}", icon="mdi:transmission-tower"),
         "groups": ["grid"]}
        for n in (1, 2, 3)
    ]
    total = {
        "key": "grid_power",
        "state": "{{ ((" + " + ".join(_grid_phase_power(n) for n in (1, 2, 3))
                 + ") / 100) | round | int }}",
        "ha": PW("Grid Power", icon="mdi:transmission-tower"),
        "groups": ["grid"],
    }
    return [*phases, total]


def rtc_template(state):
    """The RTC diagnostic sensor (upstream's `rtc`): the device clock rendered from
    the raw date/time registers, for spotting drift (see the Sync RTC button)."""
    return {"key": "rtc", "state": state,
            "ha": {"platform": "sensor", "name": "RTC", "icon": "mdi:clock",
                   "entity_category": "diagnostic", "enabled_by_default": False}}


def rtc_button(address, items):
    """A Sync RTC button (SolaX value_function_sync_rtc): on press it renders the given
    templates to consecutive registers written in one FC16 transaction."""
    return ("holding", "sync_rtc", {
        "address": address, "write_value": items,
        "ha": {"platform": "button", "name": "Sync RTC", "icon": "mdi:home-clock",
               "entity_category": "config"},
    })


# HA templates for the RTC registers. The GEN4 hybrid writes local time at 0x00; the EV
# charger writes the UTC offset (minutes, two's-complement) then UTC time at 0x61D.
RTC_LOCAL = ["{{ now().second }}", "{{ now().minute }}", "{{ now().hour }}",
             "{{ now().day }}", "{{ now().month }}", "{{ now().year % 100 }}"]
RTC_UTC = ["{{ ((now().utcoffset().total_seconds() // 60) | int) % 65536 }}",
           "{{ utcnow().second }}", "{{ utcnow().minute }}", "{{ utcnow().hour }}",
           "{{ utcnow().day }}", "{{ utcnow().month }}", "{{ utcnow().year % 100 }}"]


if __name__ == "__main__":
    # Hybrid firmware "DSP {dsp//100}.{dsp%100} ARM ..." from regs 123/124; serial is a
    # byte-swapped 7-word string at reg 0; hardware is the fixed "Gen4".
    # The PM/EPS/DCB bits pull in the entities upstream hides behind its Parallel
    # Mode / EPS / dry contact box config checkboxes; `features` maps each bit to
    # the group whose switch provides the same opt-in here (all off by default).
    run(
        "plugin_solax", lambda P: P.X3 | P.HYBRID | P.GEN4 | P.PM | P.EPS | P.DCB,
        {
            "note": "Registers follow SolaX Modbus protocol document V1.02+; the device reports "
                    "its version in the Modbus Protocol Version diagnostic sensor (holding 130).",
            "manufacturer": "SolaX Power", "model": "X3-Hybrid G4",
            "max_register_read": 100, "max_read_gap": 64, "scan_interval": 30,
            "prefix": "Solax X3-Hybrid",
            "sw_version": "DSP {{ firmware_dsp // 100 }}.{{ '%02d' | format(firmware_dsp % 100) }} "
                          "ARM {{ firmware_arm // 100 }}.{{ '%02d' | format(firmware_arm % 100) }}",
            "hw_version": "Gen4",
            "serial_number": "{{ serial }}",
            "default_groups": ["basic"],
            "group_labels": PM_GROUP_LABELS,
        },
        "Solax_X3_Hybrid_G4.yaml",
        # SolaX gates registers on the Modbus protocol *document* version (several
        # moved or changed scale at V1.00/1.01/1.02). 102 targets the current G4
        # register map; the device reports its own version in the Modbus Protocol
        # Version diagnostic sensor (holding 130) — regenerate with that value if
        # it differs.
        protocol=102,
        features=lambda P: ((P.PM, pm_groups), (P.EPS, "eps"), (P.DCB, "generator")),
        extras=[
            internal("holding", "firmware_dsp", address=123),
            internal("holding", "firmware_arm", address=124),
            internal("holding", "serial", address=0, type="string", count=7, swap="byte"),
            # grid meter power (signed: + export, - import); calibration scale defaults to identity.
            # (pv_power_total already exists as a native uint32 register on the G4.)
            ("holding", "measured_power", {"address": 70, "type": "int32", "swap": "word", "ha": PW("Measured power")}),
            rtc_button(0x00, RTC_LOCAL),  # value_function_sync_rtc: local time at 0x00-0x05
            # the inverter clock (upstream `rtc`, 6 words at 0x85): sec/min/hour/day/month/year
            internal("holding", "rtc_second", address=133),
            internal("holding", "rtc_minute", address=134),
            internal("holding", "rtc_hour", address=135),
            internal("holding", "rtc_day", address=136),
            internal("holding", "rtc_month", address=137),
            internal("holding", "rtc_year", address=138),
        ],
        # energy-flow splits SolaX computes in code — rebuilt as templates over the raw values
        templates=[
            {"key": "grid_import", "state": "{{ [-(measured_power or 0), 0] | max }}",
             "ha": PW("Grid import", icon="mdi:home-import-outline")},
            {"key": "grid_export", "state": "{{ [measured_power or 0, 0] | max }}",
             "ha": PW("Grid export", icon="mdi:home-export-outline")},
            # also behind the home_consumption group switch (upstream's ED "Home
            # Consumption Power" is this very value)
            {"key": "house_load",
             "state": "{{ (inverter_power or 0) - (measured_power or 0) + (meter_2_measured_power or 0) }}",
             "ha": PW("House load", icon="mdi:home-lightning-bolt"),
             "groups": ["advanced", "home_consumption"]},
            # PV-side alternative of the same figure (upstream house_load_alt, disabled there too)
            {"key": "house_load_alt",
             "state": "{{ (pv_power_total or 0) - (battery_power_charge or 0) - (measured_power or 0) + (meter_2_measured_power or 0) }}",
             "ha": PW("House load alt", icon="mdi:home-lightning-bolt", enabled_by_default=False)},
            {"key": "battery_charge_power", "state": "{{ [battery_power_charge or 0, 0] | max }}", "ha": PW("Battery charge power")},
            {"key": "battery_discharge_power", "state": "{{ [-(battery_power_charge or 0), 0] | max }}", "ha": PW("Battery discharge power")},
            # BMS charge-power ceiling = battery voltage x BMS max charge current (SolaX
            # value_function_bms_max_charge), falling back to the settable limit if the
            # BMS current sensor is unavailable.
            {"key": "bms_max_charge",
             "state": "{{ ((battery_voltage_charge or 0) * (bms_charge_max_current if bms_charge_max_current is not none else (battery_charge_max_current or 20))) | int }}",
             "ha": PW("BMS max charge", icon="mdi:battery-charging-high")},
            {"key": "battery_voltage_cell_difference",
             "state": "{{ ((cell_voltage_high or 0) - (cell_voltage_low or 0)) | round(3) }}",
             "ha": {"platform": "sensor", "name": "Battery voltage cell difference",
                    "device_class": "voltage", "state_class": "measurement",
                    "unit_of_measurement": "V", "enabled_by_default": False}},
            # Parallel-mode totals over the per-phase/per-string PM registers (upstream's
            # value_function_pm_total_*). House load keeps only upstream's inverter method
            # (PM power - grid power): its remote-control delta correction reads VPP
            # registers we don't convert. The current totals sum at the registers'
            # 0.1 A resolution where upstream truncates each phase to whole amps.
            {"key": "pm_total_inverter_power",
             "state": "{{ ((pm_activepower_l1 or 0) + (pm_activepower_l2 or 0) + (pm_activepower_l3 or 0)) | int }}",
             "ha": PW("PM Total Inverter Power", icon="mdi:home-lightning-bolt"),
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            {"key": "pm_total_pv_power",
             "state": "{{ ((pm_pv_power_1 or 0) + (pm_pv_power_2 or 0)) | int }}",
             "ha": PW("PM Total PV Power", icon="mdi:solar-power"),
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            {"key": "pm_total_house_load",
             "state": "{{ ((pm_activepower_l1 or 0) + (pm_activepower_l2 or 0) + (pm_activepower_l3 or 0) - (measured_power or 0)) | int }}",
             "ha": PW("PM Total House Load", icon="mdi:home-lightning-bolt"),
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            {"key": "pm_total_reactive_or_apparentpower",
             "state": "{{ ((pm_reactive_or_apparentpower_l1 or 0) + (pm_reactive_or_apparentpower_l2 or 0) + (pm_reactive_or_apparentpower_l3 or 0)) | int }}",
             "ha": {"platform": "sensor", "name": "PM Total Reactive or ApparentPower",
                    "device_class": "apparent_power", "state_class": "measurement",
                    "unit_of_measurement": "VA", "icon": "mdi:flash"},
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            {"key": "pm_total_inverter_current",
             "state": "{{ ((pm__current_l1 or 0) + (pm__current_l2 or 0) + (pm__current_l3 or 0)) | round(1) }}",
             "ha": {"platform": "sensor", "name": "PM Total Inverter Current",
                    "device_class": "current", "state_class": "measurement",
                    "unit_of_measurement": "A", "icon": "mdi:current-ac"},
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            {"key": "pm_total_pv_current",
             "state": "{{ ((pm_pv_current_1 or 0) + (pm_pv_current_2 or 0)) | round(1) }}",
             "ha": {"platform": "sensor", "name": "PM Total PV Current",
                    "device_class": "current", "state_class": "measurement",
                    "unit_of_measurement": "A", "icon": "mdi:current-dc"},
             "groups": ["pm_i1", "pm_i2", "pm_i3"]},
            # Upstream's three Energy Dashboard switches, mapped to groups over
            # real entities instead of the copies upstream creates. The kWh
            # sensors integrate power over time (`integrate`, like upstream's
            # Riemann sums) where the device offers no native counter;
            # grid_to_battery_power mirrors upstream's max(-inverter_power, 0).
            {"key": "grid_to_battery_power",
             "state": "{{ [-(inverter_power or 0), 0] | max }}",
             "ha": PW("Grid to Battery Power", icon="mdi:transmission-tower-export"),
             "groups": ["grid_to_battery"]},
            {"key": "pv_energy_1",
             "state": "{{ [pv_power_1 or 0, 0] | max }}",
             "integrate": "trapezoidal",
             "ha": KWH("PV Energy 1", icon="mdi:solar-power"),
             "groups": ["solar_details"]},
            {"key": "pv_energy_2",
             "state": "{{ [pv_power_2 or 0, 0] | max }}",
             "integrate": "trapezoidal",
             "ha": KWH("PV Energy 2", icon="mdi:solar-power"),
             "groups": ["solar_details"]},
            # the house_load formula, clamped to consumption (upstream filters
            # its Riemann source the same way)
            {"key": "home_consumption_energy",
             "state": "{{ [(inverter_power or 0) - (measured_power or 0) + (meter_2_measured_power or 0), 0] | max }}",
             "integrate": "trapezoidal",
             "ha": KWH("Home Consumption Energy", icon="mdi:home-lightning-bolt"),
             "groups": ["home_consumption"]},
            # Per-phase + total real grid power for the `grid` group (the V/I
            # sensors it reveals have no power register on the device).
            *grid_power_templates(),
            rtc_template("{{ '20%02d-%02d-%02d %02d:%02d:%02d' | format(rtc_year, rtc_month, rtc_day, rtc_hour, rtc_minute, rtc_second) }}"),
        ],
        basic=HYBRID_BASIC,
        extra_groups=HYBRID_EXTRA_GROUPS,
    )
    # Charger firmware "ARM v{version/100}" from reg 37; hardware fixed "Gen2".
    run(
        "plugin_solax_ev_charger", lambda P: P.X3 | P.POW11 | P.GEN2,
        {
            "manufacturer": "SolaX Power", "model": "X3-HAC (11 kW)",
            "max_register_read": 32, "max_read_gap": 64, "scan_interval": 30,
            "prefix": "Solax X3-HAC",
            "sw_version": "ARM v{{ '%.2f' | format(firmware_version / 100) }}",
            "hw_version": "Gen2",
            "default_groups": ["basic"],
        },
        "Solax_X3_HAC.yaml",
        extras=[
            # upstream reads FirmwareVersion from INPUT 0x25 (its callable scale
            # blocks auto-conversion; the /100 lives in the sw_version template)
            internal("input", "firmware_version", address=37),
            rtc_button(0x61D, RTC_UTC),  # value_function_sync_rtc_evc: tz + UTC time at 0x61D
            # the charger clock (upstream `rtc`, 7 words at 0x61D): the timezone
            # offset in minutes (two's-complement), then sec/min/hour/day/month/year
            internal("holding", "rtc_tz", address=1565),
            internal("holding", "rtc_second", address=1566),
            internal("holding", "rtc_minute", address=1567),
            internal("holding", "rtc_hour", address=1568),
            internal("holding", "rtc_day", address=1569),
            internal("holding", "rtc_month", address=1570),
            internal("holding", "rtc_year", address=1571),
        ],
        templates=[
            # the stored time with its stored UTC offset, no conversion (upstream rtc)
            rtc_template(
                "{% set tz = rtc_tz - 65536 if rtc_tz > 32767 else rtc_tz %}"
                "{{ '20%02d-%02d-%02d %02d:%02d:%02d UTC%s%02d:%02d' | format(rtc_year, rtc_month, rtc_day, "
                "rtc_hour, rtc_minute, rtc_second, '+' if tz >= 0 else '-', (tz | abs) // 60, (tz | abs) % 60) }}"
            ),
        ],
        basic=HAC_BASIC,
    )
