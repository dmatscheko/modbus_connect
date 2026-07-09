#!/usr/bin/env python3
"""Convert homeassistant-solax-modbus plugin entity descriptions -> modbus_connect YAML.

Unlike ``modbus_local_gateway-convert.py`` this is NOT standalone: it imports the
upstream SolaX plugin modules, so it needs Home Assistant installed and a checkout of
https://github.com/wills106/homeassistant-solax-modbus. It filters the entity
descriptions to a target inverter spec (bitmask) and emits our declarative device-config
format, skipping computed/local entities (no real register, value_function, callable
scale, write_method=local) and reporting what it dropped. Regenerates the bundled
Solax_X3_Hybrid_G4.yaml and Solax_X3_HAC.yaml.

Usage (point SOLAX_MODBUS_REPO at your checkout, else the default path is used):

    SOLAX_MODBUS_REPO=/path/to/homeassistant-solax-modbus \\
        python3 converter/homeassistant_solax_modbus-convert.py
"""
import importlib
import os
import sys
import types
from collections import Counter
from pathlib import Path

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


# solax register_data_type -> (our type | None for uint16 default, swap, mask)
DTYPE = {
    "_uint16": (None, None, None),
    "_int16": ("int16", None, None),
    "_uint32": ("uint32", "word", None),
    "_int32": ("int32", "word", None),
    "_float32": ("float32", "word", None),
    "_ulsb16msb16": ("uint32", "word", None),
    "_int8L": (None, None, 0x00FF),
    "_int8H": (None, None, 0xFF00),
    "_string": ("string", None, None),
}
WRITE_LOCAL = 3
# write_method 2 (MULTISINGLE) and 4 (MULTI) both use FC16. Registers written this
# way are "direct" command registers with no read-back — write-only in our terms.
WRITE_FC16 = (2, 4)


def make_static(e, b, ha, option_map):
    """A write-only command register: FC16, never read, always shows the seeded value
    (from initvalue) and off by default (advanced/expert direct-control registers).
    The presence of static_value marks the entity write-only."""
    b["write_multiple"] = True
    iv = getattr(e, "initvalue", None)
    if option_map is not None:  # select: seed is an option label
        b["static_value"] = str(option_map.get(iv, next(iter(option_map.values()))))
    else:  # number: seed is the numeric initvalue (0 if unset)
        b["static_value"] = iv if iv is not None else 0
    ha["enabled_by_default"] = False


def base_fields(e):
    """Modbus-level fields shared by all register-backed entities. Returns None if unconvertible."""
    reg = getattr(e, "register", None)
    if reg is None or reg < 0:
        return None  # computed / local-only
    dtype = getattr(e, "register_data_type", None) or "_uint16"
    if dtype in ("_words",) or dtype not in DTYPE:
        return None
    typ, swap, mask = DTYPE[dtype]
    out = {"address": reg}
    if typ:
        out["type"] = typ
    if dtype == "_string":
        out["count"] = getattr(e, "wordcount", None) or 1
    if swap:
        out["swap"] = swap
    if mask is not None:
        out["mask"] = mask
    return out


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
    return ha


def table_of(e):
    return "holding" if e.register_type == 1 else "input"


def apply_scale(e, b, ha):
    """Fold SolaX's scale onto the modbus base + ha block. Returns True if the scale
    is a value_function (callable) we can't express, making this a read source only."""
    scale = getattr(e, "scale", 1)
    if callable(scale):
        return True  # register-only read source; a merging writable supplies the conversion
    if isinstance(scale, dict):
        b["map"] = {int(k): str(v) for k, v in scale.items()}
        return False
    mult = float(scale) * float(getattr(e, "read_scale", 1) or 1)
    if mult != 1:
        b["multiplier"] = round(mult, 10)
    if 0 < mult < 1 and ha.get("unit_of_measurement") is not None:
        ha["precision"] = getattr(e, "rounding", 1)
    return False


class _Converter:
    """Accumulates converted entities across the SolaX entity-description tables.

    SolaX gives each writable setting a read-back *sensor* and a *number/select* at
    DIFFERENT registers. We read from the sensor's register and write to the number/
    select's (address / write_address) rather than dropping either. The per-table
    handlers below share the read index and dedupe/skip bookkeeping held here; each
    handles one entity so no single one carries the whole pipeline's complexity.
    """

    def __init__(self, pi, spec):
        self.pi = pi
        self.spec = spec
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

    def match(self, e):
        return self.pi.matchInverterWithMask(self.spec, e.allowedtypes)

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
        # two ends of a setting share the same map/multiplier. Never borrow onto a
        # source that already has the other kind: map+multiplier cannot combine.
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
        if getattr(e, "write_method", 1) in WRITE_FC16:
            make_static(e, b, ha, omap)
        else:
            # A writable may name its companion read-back sensor via sensor_key.
            self.link_readback(getattr(e, "sensor_key", None) or e.key, "holding", b)
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
        b = base_fields(e)
        if b is None:
            self.skipped["sensor:no-register"] += 1
            return
        ha = ha_common(e, "sensor")
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
        b = base_fields(e)
        if b is None:
            self.skipped["select:no-register"] += 1
            return
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
        b = base_fields(e)
        if b is None:
            self.skipped["number:no-register"] += 1
            return
        scale = float(getattr(e, "scale", 1) or 1)
        if scale != 1:
            b["multiplier"] = round(scale, 10)
        ha = ha_common(e, "number")
        ha["min"], ha["max"] = lo, hi
        if getattr(e, "native_step", None) is not None:
            ha["step"] = e.native_step
        self._emit_writable(e, b, ha, None)

    def add_time(self, e):
        """A time. GEN4 packs HH:MM in one register (hour*256 + minute); the EV
        charger uses two registers (hour, then minute) -> our ``count: 2`` form."""
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
        # rectify_time: a stop time of 24:00 (end of day) shows as 23:59 rather than
        # dropping out — otherwise that slot would be unavailable.
        b = {"address": reg, "type": "time", "rectify_time": True, "ha": ha_common(e, "time")}
        if wordcount == 2:  # separate registers: first = hour, second = minute
            b["count"] = 2
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
        b = {"address": e.register, "write_value": e.command, "ha": ha_common(e, "button")}
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


def convert(pi, spec):
    """Convert a plugin's entity descriptions for one inverter spec into our
    declarative entities. See :class:`_Converter` for how a setting's split
    read/write registers are recombined."""
    return _Converter(pi, spec).run()


# --- entity groups -----------------------------------------------------------
#
# Each entity/template is tagged with the tiers it belongs to so the integration's
# group switches can show a subset. Tiers are independent groups (an entity is
# shown if any of its groups is enabled); nesting is expressed by listing every
# tier it belongs to. A hand-curated "basic" set is the minimal everyday view;
# everything SolaX enables by default is "advanced"; everything (incl. the hidden
# expert entities) is in "all". The device defaults to showing only "basic".

# The keys that make up the everyday view of each device (basic ⊆ advanced ⊆ all).
HYBRID_BASIC = frozenset({
    "run_mode", "pv_power_total", "pv_power_1", "pv_power_2",
    "pv_voltage_1", "pv_voltage_2", "inverter_power", "inverter_temperature",
    "battery_power_charge", "battery_capacity", "bdc_status",
    "today_s_solar_energy", "total_solar_energy", "total_yield",
    "battery_input_energy_today", "battery_output_energy_today",
    "grid_import", "grid_export",
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


def tier_groups(key, ha, basic):
    """The group tags for one entity/template: basic (also advanced, all) if it is
    in the curated set, else advanced (and all) if enabled by default, else all."""
    if key in basic:
        return ["basic", "advanced", "all"]
    enabled = ha.get("enabled_by_default", True) is not False
    return ["advanced", "all"] if enabled else ["all"]


def annotate_groups(entities, templates, basic):
    """Attach group tags to every non-internal entity and every template in place.
    Internal read-only entities carry none (never shown; always polled when needed).
    A curated basic entity is forced enabled — SolaX ships a few of them disabled,
    but if we put one in the everyday view it should show without extra clicks."""
    for _table, key, b in entities:
        if b.get("internal"):
            continue
        ha = b.get("ha", {})
        if key in basic:
            ha.pop("enabled_by_default", None)
        b["groups"] = tier_groups(key, ha, basic)
    for t in templates:
        t["groups"] = tier_groups(t["key"], t.get("ha", {}), basic)


# Entity fields emitted (in order) before the map / read_register / ha blocks.
EMIT_FIELDS = (
    "address", "type", "count", "swap", "mask", "sum_scale", "multiplier",
    "write_value", "static_value", "optimistic_default", "write_multiple",
    "rectify_time", "scan_interval", "groups",
)


def _emit_mapping(buf, indent, mapping):
    """Write a flat ``key: value`` block at the given indent."""
    for k, v in mapping.items():
        buf.write(f"{indent}{k}: {yaml_str(v)}\n")


def _emit_field(buf, name, value):
    """One entity field. A list write_value becomes a YAML sequence (multi-register
    button); groups become an inline flow list."""
    if name == "write_value" and isinstance(value, list):
        buf.write("    write_value:\n")
        for item in value:
            buf.write(f"      - {yaml_str(item)}\n")
    elif name == "groups":
        buf.write(f"    groups: [{', '.join(value)}]\n")
    else:
        buf.write(f"    {name}: {yaml_str(value)}\n")


def _emit_entity(buf, key, b):
    """Emit one register entity: scalar fields, optional map/read_register, then either
    the internal marker or its ha block."""
    buf.write(f"  {key}:\n")
    for f in EMIT_FIELDS:
        if f in b:
            _emit_field(buf, f, b[f])
    if "map" in b:
        buf.write("    map:\n")
        _emit_mapping(buf, "      ", b["map"])
    if "read_register" in b:
        buf.write(f"    read_register: {yaml_str(b['read_register'])}\n")
    if b.get("internal"):
        buf.write("    internal: true\n")
        return
    buf.write("    ha:\n")
    _emit_mapping(buf, "      ", b["ha"])


def _emit_table(buf, table, entities):
    """Emit every entity of one table, sorted by address."""
    rows = sorted(
        [(k, b) for t, k, b in entities if t == table],
        key=lambda kb: kb[1]["address"],
    )
    if not rows:
        return
    buf.write(f"\n{table}:\n")
    for key, b in rows:
        _emit_entity(buf, key, b)


def _emit_templates(buf, templates):
    """Emit the computed-sensor ``template:`` section (energy-flow splits)."""
    if not templates:
        return
    buf.write("\n# Computed sensors (energy-flow splits SolaX derives in code).\n")
    buf.write("template:\n")
    for t in templates:
        buf.write(f"  {t['key']}:\n")
        buf.write("    ha:\n")
        _emit_mapping(buf, "      ", t["ha"])
        buf.write(f"    state: {yaml_str(t['state'])}\n")
        if t.get("groups"):
            buf.write(f"    groups: [{', '.join(t['groups'])}]\n")


def emit_yaml(meta, entities, templates=()):
    import io
    buf = io.StringIO()
    buf.write("# Generated from homeassistant-solax-modbus by solax_convert.py — review before use.\n")
    buf.write("device:\n")
    meta = dict(meta)
    default_groups = meta.pop("default_groups", None)
    split_before = meta.pop("split_before", None)
    _emit_mapping(buf, "  ", meta)
    if split_before:
        inner = ", ".join(
            f"{table}: [{', '.join(str(a) for a in addrs)}]"
            for table, addrs in split_before.items()
        )
        buf.write(f"  split_before: {{ {inner} }}\n")
    if default_groups:
        buf.write(f"  default_groups: [{', '.join(default_groups)}]\n")
    for table in ("holding", "input"):
        _emit_table(buf, table, entities)
    _emit_templates(buf, templates)
    return buf.getvalue()


def yaml_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        s = repr(v)
        # YAML's float syntax needs a dot in the mantissa and a signed exponent;
        # repr(1e-05) = '1e-05' would load back as a *string*.
        if "e" in s:
            mantissa, _, exponent = s.partition("e")
            if "." not in mantissa:
                mantissa += ".0"
            if exponent[0] not in "+-":
                exponent = "+" + exponent
            s = f"{mantissa}e{exponent}"
        return s
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if (
        s == ""
        or any(c in s for c in ":#%°'\"\\{}[],&*!|>@")
        or s[0] in "-+. "
        or s[-1] == " "
        or s[0].isdigit()
        or s.lower() in ("null", "true", "false", "yes", "no", "on", "off")
    ):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


DEST = str(
    Path(__file__).resolve().parent.parent
    / "custom_components/modbus_connect/device_configs"
)


def validate_output(text, filename):
    """Round-trip the emitted YAML through the integration's schema, so an emitter
    bug fails the conversion loudly instead of the config entry later."""
    import yaml

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components"))
    from modbus_connect.schema import parse_device

    parse_device(yaml.safe_load(text), filename=filename)


def run(module, spec_fn, meta, filename, extras=(), templates=(), basic=frozenset()):
    P = load_plugin(module)
    ents, skipped, boundaries = convert(P.plugin_instance, spec_fn(P))
    ents = list(ents) + list(extras)  # device-info + computed registers, appended post-dedupe
    dupes = [k for k, n in Counter(k for _, k, _ in ents).items() if n > 1]
    if dupes:  # extras bypass the converter's dedupe; a repeat would silently last-win
        raise SystemExit(f"{filename}: duplicate entity keys {sorted(dupes)}")
    annotate_groups(ents, templates, basic)
    if boundaries:
        meta = dict(meta)
        split = {}
        for table, addr in sorted(boundaries):
            split.setdefault(table, []).append(addr)
        meta["split_before"] = split
    text = emit_yaml(meta, ents, templates)
    validate_output(text, filename)
    with open(f"{DEST}/{filename}", "w", encoding="utf-8") as f:
        f.write(text)
    plat = Counter(b.get("ha", {}).get("platform", "internal") for _, _, b in ents)
    print(f"\nWROTE {filename}: {dict(plat)} +{len(templates)} template total {len(ents) + len(templates)}")
    print("  skipped:", {k: v for k, v in skipped.items() if v})


def internal(table, key, **fields):
    return (table, key, {**fields, "internal": True})


def PW(name):
    """A power-sensor ha block (W, measurement)."""
    return {"platform": "sensor", "name": name, "device_class": "power",
            "state_class": "measurement", "unit_of_measurement": "W"}


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
    run(
        "plugin_solax", lambda P: P.X3 | P.HYBRID | P.GEN4,
        {
            "manufacturer": "SolaX Power", "model": "X3-Hybrid G4",
            "max_register_read": 100, "max_read_gap": 64, "scan_interval": 30,
            "prefix": "Solax X3-Hybrid",
            "sw_version": "DSP {{ firmware_dsp // 100 }}.{{ '%02d' | format(firmware_dsp % 100) }} "
                          "ARM {{ firmware_arm // 100 }}.{{ '%02d' | format(firmware_arm % 100) }}",
            "hw_version": "Gen4",
            "serial_number": "{{ serial }}",
            "default_groups": ["basic"],
        },
        "Solax_X3_Hybrid_G4.yaml",
        extras=[
            internal("holding", "firmware_dsp", address=123),
            internal("holding", "firmware_arm", address=124),
            internal("holding", "serial", address=0, type="string", count=7, swap="byte"),
            # grid meter power (signed: + export, - import); calibration scale defaults to identity.
            # (pv_power_total already exists as a native uint32 register on the G4.)
            ("holding", "measured_power", {"address": 70, "type": "int32", "swap": "word", "ha": PW("Measured power")}),
            rtc_button(0x00, RTC_LOCAL),  # value_function_sync_rtc: local time at 0x00-0x05
        ],
        # energy-flow splits SolaX computes in code — rebuilt as templates over the raw values
        templates=[
            {"key": "grid_import", "state": "{{ [-(measured_power or 0), 0] | max }}", "ha": PW("Grid import")},
            {"key": "grid_export", "state": "{{ [measured_power or 0, 0] | max }}", "ha": PW("Grid export")},
            {"key": "house_load", "state": "{{ (inverter_power or 0) - (measured_power or 0) }}", "ha": PW("House load")},
            {"key": "battery_charge_power", "state": "{{ [battery_power_charge or 0, 0] | max }}", "ha": PW("Battery charge power")},
            {"key": "battery_discharge_power", "state": "{{ [-(battery_power_charge or 0), 0] | max }}", "ha": PW("Battery discharge power")},
            # BMS charge-power ceiling = battery voltage x BMS max charge current (SolaX
            # value_function_bms_max_charge), falling back to the settable limit if the
            # BMS current sensor is unavailable.
            {"key": "bms_max_charge",
             "state": "{{ ((battery_voltage_charge or 0) * (bms_charge_max_current if bms_charge_max_current is not none else (battery_charge_max_current or 20))) | int }}",
             "ha": PW("BMS max charge")},
        ],
        basic=HYBRID_BASIC,
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
        ],
        basic=HAC_BASIC,
    )
