#!/usr/bin/env python3
"""Generate support/devicedocs/<folder>/registers.md for each bundled device file.

The register table is derived from the integration's own device YAML (the ground
truth of what Modbus Connect reads/writes), so the "Modbus command" and
"data type / conversion" columns reflect real behaviour. The primary-source
block at the top is filled from a sources JSON (folder -> metadata) collected by
the research agents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
CFG_DIR = REPO / "custom_components/modbus_connect/device_configs"
OUT_DIR = REPO / "support/devicedocs"

# ---- mirror of the integration's type/FC model (models.py / client.py) ----
TYPE_BITS = {
    "bit": 1, "uint8": 8, "int8": 8, "uint16": 16, "int16": 16,
    "uint32": 32, "int32": 32, "uint64": 64, "int64": 64,
    "float16": 16, "float32": 32, "float64": 64,
}
TYPE_WIDTH = {t: max(1, b // 16) for t, b in TYPE_BITS.items()}
WRITING_PLATFORMS = {"number", "select", "switch", "text", "time", "button", "valve"}
WRITABLE_TABLES = {"holding", "coil"}
BIT_TABLES = {"coil", "discrete"}

# table -> (label, prefix, read-FC)
TABLE_META = {
    "holding": ("Holding", "4x", "FC03"),
    "input": ("Input", "3x", "FC04"),
    "coil": ("Coil", "0x", "FC01"),
    "discrete": ("Discrete", "1x", "FC02"),
}
TABLE_ORDER = ["holding", "input", "coil", "discrete"]

# config filename -> kebab-case device folder (single source of truth: device_folders.json,
# also read by augment.py to locate each device's augment.yaml policy). Test.yaml maps to
# "test" but is excluded from generated docs (example only, no public register document).
CONFIG_TO_FOLDER = json.loads(
    (Path(__file__).resolve().parent / "device_folders.json").read_text(encoding="utf-8")
)
DOC_EXCLUDED = {"test"}


def fmtnum(x) -> str:
    if isinstance(x, float):
        s = f"{x:.10g}"
        return s
    return str(x)


def platform_of(params: dict) -> str:
    if params.get("internal") is True:
        return "internal"
    ha = params.get("ha") or {}
    return ha.get("platform", "")


def write_word_count(params: dict) -> int:
    wv = params.get("write_value")
    if isinstance(wv, list):
        return len(wv)
    t = params.get("type", "uint16")
    if t == "string":
        return int(params.get("count", 1) or 1)
    if t == "time":
        return 2 if params.get("count") == 2 else 1
    return TYPE_WIDTH.get(t, 1)


def command_cell(table: str, params: dict) -> str:
    plat = platform_of(params)
    read_fc = TABLE_META[table][2]
    writes = (plat in WRITING_PLATFORMS) and (table in WRITABLE_TABLES)
    static = params.get("static_value") is not None
    has_readreg = params.get("read_register") is not None
    is_button = plat == "button"
    polls = (not is_button) and (not has_readreg) and (not static)

    if writes:
        if table == "coil":
            wfc, note = "FC05", ""
        else:
            n = write_word_count(params)
            forced = params.get("write_multiple") is True
            if n > 1:
                wfc, note = "FC16", ""
            elif forced:
                wfc, note = "FC16", " (forced write-multiple)"
            else:
                wfc, note = "FC06", ""
        if not polls and has_readreg:
            return f"{wfc} write{note} · read-back elsewhere"
        if not polls:  # button / static_value command register
            return f"{wfc} write-only{note}"
        return f"{read_fc} read · {wfc} write{note}"

    # read-only
    return f"{read_fc} read"


def conv_cell(table: str, params: dict) -> str:
    t = params.get("type")
    parts: list[str] = []
    if table in BIT_TABLES:
        base = "bool (bit)"
    elif t == "string":
        c = int(params.get("count", 0) or 0)
        base = f"string · {c} regs ({c * 2} chars)"
    elif t == "time":
        base = "time hh:mm" + (" · 2 regs" if params.get("count") == 2 else "")
    else:
        base = t or "uint16"
    parts.append(base)

    if params.get("swap"):
        parts.append(f"swap {params['swap']}")
    m = params.get("multiplier")
    if m is not None and m != 1:
        parts.append(f"×{fmtnum(m)}")  # noqa: RUF001  (multiplication sign is intentional)
    o = params.get("offset")
    if o is not None and o != 0:
        sign = "+" if (isinstance(o, (int, float)) and o >= 0) else ""
        parts.append(f"{sign}{fmtnum(o)}")
    if params.get("mask") is not None:
        mask = params["mask"]
        parts.append(f"mask 0x{mask:X}" if isinstance(mask, int) else f"mask {mask}")
    if params.get("map") is not None:
        parts.append(f"enum · {len(params['map'])} opts")
    if params.get("flags") is not None:
        parts.append(f"bitfield · {len(params['flags'])} flags")
    if params.get("sum_scale") is not None:
        parts.append(f"sum_scale {params['sum_scale']}")
    if table not in BIT_TABLES and platform_of(params) in ("switch", "binary_sensor"):
        on = params.get("on_value")
        if on is not None:
            parts.append(f"on={on}")
    return " · ".join(parts)


def reg_cell(key: str, params: dict) -> str:
    addr = params["address"]
    ha = params.get("ha") or {}
    name = ha.get("name")
    label = name or key
    cell = f"`0x{addr:04X}` ({addr}) — {label}"
    if params.get("internal") is True:
        cell += " _(internal)_"
    if name and name != key:
        cell += f"<br>`{key}`"
    return cell


def md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def build_table(cfg: dict) -> tuple[str, dict]:
    rows = []
    counts = dict.fromkeys(TABLE_ORDER, 0)
    for table in TABLE_ORDER:
        section = cfg.get(table)
        if not isinstance(section, dict):
            continue
        for key, params in section.items():
            if not isinstance(params, dict) or "address" not in params:
                continue
            counts[table] += 1
            label, prefix, _ = TABLE_META[table]
            rows.append(
                "| {reg} | {tbl} | {cmd} | {conv} |".format(
                    reg=md_escape(reg_cell(key, params)),
                    tbl=f"{label} ({prefix})",
                    cmd=md_escape(command_cell(table, params)),
                    conv=md_escape(conv_cell(table, params)),
                )
            )
    header = (
        "| Register | Table | Modbus command | Data type / conversion |\n"
        "| --- | --- | --- | --- |"
    )
    return header + "\n" + "\n".join(rows), counts


def human_size(n: int) -> str:
    n = float(n)
    if n < 1024:
        return f"{int(n)} bytes"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


# Repo-generated / tooling files that share the device folder but are NOT manufacturer
# source documents, so they never appear in the "Local copy" list.
_NON_SOURCE_FILES = {"registers.md", "groups.md", "caveats.md", "augment.yaml"}


def local_files(folder: str, primary: str | None) -> list[str]:
    """Downloaded manufacturer docs on disk (excluding repo-generated/policy files), primary first."""
    d = OUT_DIR / folder
    if not d.exists():
        return []
    files = [f for f in sorted(d.iterdir()) if f.is_file() and f.name not in _NON_SOURCE_FILES]
    files.sort(key=lambda f: (f.name != primary, f.name.lower()))
    return files


def source_block(folder: str, sources: dict) -> str:
    s = sources.get(folder) or {}
    files = local_files(folder, s.get("primary_file"))
    file_lines = []
    for f in files:
        size = human_size(f.stat().st_size)
        tag = " — primary source" if s.get("primary_file") == f.name and len(files) > 1 else ""
        name = f.name.replace(" ", "%20")
        file_lines.append(f"- Local copy: [`{f.name}`](./{name}) — {size}{tag}")

    lines = ["## Primary source", ""]
    if not s or s.get("source_type") == "none" or not s.get("url"):
        lines.append(
            "No public primary-source register document from the manufacturer "
            "could be confirmed for this device."
        )
        if s.get("url"):
            lines.append("")
            lines.append(f"- Best available reference: [{s['url']}]({s['url']})")
        if file_lines:
            lines.append("")
            lines.extend(file_lines)
        if s.get("notes"):
            lines.append("")
            lines.append(f"> {s['notes']}")
        return "\n".join(lines)

    title = s.get("title") or "Modbus protocol / register document"
    ver = s.get("version")
    ver_txt = f" ({ver})" if ver and str(ver).lower() != "unknown" else ""
    lines.append(f"- **{title}**{ver_txt}")
    lines.append(f"- Source: [{s['url']}]({s['url']})")
    for extra in s.get("extra_urls", []):
        lines.append(f"- Also: [{extra}]({extra})")
    st = s.get("source_type", "")
    if st:
        lines.append(f"- Source type: {st}")
    if s.get("match"):
        lines.append(f"- Register addresses vs device file: {s['match']}")
    lines.extend(file_lines)
    if s.get("notes"):
        lines.append("")
        lines.append(f"> {s['notes']}")
    return "\n".join(lines)


def gen_one(cfg_path: Path, folder: str, sources: dict) -> str:
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    dev = cfg.get("device", {})
    manuf = dev.get("manufacturer", "")
    model = dev.get("model", "")
    table_md, counts = build_table(cfg)
    n_tmpl = len(cfg.get("template", {}) or {})

    total = sum(counts.values())
    present = [f"{TABLE_META[t][0]} {counts[t]}" for t in TABLE_ORDER if counts[t]]

    out = []
    out.append(f"# {manuf} {model} — Modbus registers")
    out.append("")
    out.append(f"**Device file:** `custom_components/modbus_connect/device_configs/{cfg_path.name}`")
    out.append("")
    out.append(source_block(folder, sources))
    out.append("")
    out.append("## Scope & conventions")
    out.append("")
    out.append(
        "This table lists the **registers used by Modbus Connect's device file** — "
        "what the integration actually reads and writes. The manufacturer's document "
        "linked above is the authoritative, complete register map; consult it for "
        "registers this integration does not use."
    )
    out.append("")
    out.append(
        "Tables (as named in the datasheet): **Holding** (4x — FC03 read, "
        "FC06/FC16 write), **Input** (3x — FC04, read-only), **Coil** (0x — FC01 "
        "read, FC05 write), **Discrete** (1x — FC02, read-only). The *Modbus "
        "command* column shows the function codes this integration uses; it notes "
        "where a single register is written with FC16 (write-multiple) because the "
        "device requires it. *(internal)* registers are polled to feed composite "
        "template entities but expose no entity of their own."
    )
    out.append("")
    out.append(
        f"**Registers in this file:** {total}"
        + (f" ({', '.join(present)})" if present else "")
        + (f" · plus {n_tmpl} composite template entities" if n_tmpl else "")
    )
    out.append("")
    out.append("## Registers")
    out.append("")
    out.append(table_md)
    out.append("")
    return "\n".join(out)


def main() -> None:
    # Source metadata is the sibling sources.json; positional args (if any) limit
    # generation to those device folders.
    sources_path = Path(__file__).resolve().parent / "sources.json"
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    for cfg_name, folder in CONFIG_TO_FOLDER.items():
        if folder in DOC_EXCLUDED:
            continue
        if only and folder not in only:
            continue
        cfg_path = CFG_DIR / cfg_name
        if not cfg_path.exists():
            print(f"!! missing config {cfg_name}", file=sys.stderr)
            continue
        md = gen_one(cfg_path, folder, sources)
        dest_dir = OUT_DIR / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "registers.md").write_text(md, encoding="utf-8")
        print(f"wrote {folder}/registers.md ({len(md)} bytes)")


if __name__ == "__main__":
    main()
