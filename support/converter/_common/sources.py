#!/usr/bin/env python3
"""Parsers for the downloaded manufacturer source documents under
``support/devicedocs/<device>/``.

Provides:
  * ``read_xlsx`` / ``pichler_records`` — the Pichler LS-Control Modbus xlsx
    (Setpoints / Datapoints sheets).
  * ``parse_html_rows`` / ``dimplex_datapoints`` — the Dimplex NWPM Modbus-TCP
    datapoint list (saved HTML).

Pure standard library (+ nothing else) so it runs without extra installs.
Run directly for a quick self-test:  ``python3 sources.py``
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEVDOCS = REPO / "support" / "devicedocs"
CFG = REPO / "custom_components" / "modbus_connect" / "device_configs"

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


# --------------------------------------------------------------------------- #
# xlsx (Pichler LS-Control Modbus lists)
# --------------------------------------------------------------------------- #
def _col_idx(ref: str) -> int:
    letters = re.match(r"([A-Z]+)", ref).group(1)
    c = 0
    for ch in letters:
        c = c * 26 + (ord(ch) - 64)
    return c - 1


def read_xlsx(path: Path) -> dict[str, list[list]]:
    """Return {sheet_name: [row, ...]} where row is a list of cell values."""
    z = zipfile.ZipFile(path)
    sst: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{_M}si"):
            sst.append("".join(t.text or "" for t in si.iter(f"{_M}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {r.get("Id"): r.get("Target") for r in rels}
    out: dict[str, list[list]] = {}
    for sh in wb.find(f"{_M}sheets"):
        target = relmap[sh.get(f"{_R}id")]
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{_M}row"):
            cells: dict[int, str] = {}
            for c in row.findall(f"{_M}c"):
                ci = _col_idx(c.get("r"))
                t = c.get("t")
                v = c.find(f"{_M}v")
                val = None
                if t == "s" and v is not None:
                    val = sst[int(v.text)]
                elif t == "inlineStr":
                    is_ = c.find(f"{_M}is")
                    val = "".join(x.text or "" for x in is_.iter(f"{_M}t")) if is_ is not None else None
                elif v is not None:
                    val = v.text
                cells[ci] = val
            rows.append([cells.get(i) for i in range(max(cells) + 1 if cells else 0)])
        out[sh.get("name")] = rows
    return out


def _find_xlsx(folder: str) -> Path:
    files = sorted((DEVDOCS / folder).glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"no .xlsx in support/devicedocs/{folder}/")
    return files[0]


def pichler_records(folder: str, sheet: str) -> list[dict]:
    """Records from a Pichler xlsx sheet ('Setpoints' or 'Datapoints').

    Each record is the header->cell dict plus ``_addr`` (int address). The
    header row is the one whose first cell is 'Name'.
    """
    rows = read_xlsx(_find_xlsx(folder))[sheet]
    hi = next(i for i, r in enumerate(rows) if r and str(r[0]).strip() == "Name")
    hdr = [str(c or "").strip() for c in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        if not r or not r[0]:
            continue
        rec = {hdr[i] if i < len(hdr) else f"c{i}": (str(r[i]).strip() if i < len(r) and r[i] is not None else "")
               for i in range(max(len(hdr), len(r)))}
        addr = rec.get("Address") or rec.get("Modbus Adress") or ""
        m = re.match(r"-?\d+", addr)
        if not m:
            continue
        rec["_addr"] = int(m.group())
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# HTML (Dimplex NWPM Modbus-TCP datapoint list)
# --------------------------------------------------------------------------- #
_ENT = {"&uuml;": "ü", "&ouml;": "ö", "&auml;": "ä", "&Uuml;": "Ü", "&Ouml;": "Ö",
        "&Auml;": "Ä", "&szlig;": "ß", "&deg;": "°", "&nbsp;": " ", "&amp;": "&"}


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    for k, v in _ENT.items():
        s = s.replace(k, v)
    return re.sub(r"\s+", " ", s).strip()


def parse_html_rows(path: Path) -> list[list[str]]:
    html = path.read_text(encoding="utf8")
    rows = []
    for tr in re.findall(r"<tr\b.*?</tr>", html, re.S):
        rows.append([_strip_html(td) for td in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, re.S)])
    return rows


def _dimplex_html() -> Path:
    files = sorted((DEVDOCS / "dimplex-si-11tu").glob("*.html"))
    if not files:
        raise FileNotFoundError("no Dimplex NWPM .html in support/devicedocs/dimplex-si-11tu/")
    return files[0]


def dimplex_datapoints() -> list[dict]:
    """Deduplicated datapoints from the Dimplex NWPM datapoint list.

    Each row is anchored on its R/W cell (the table has an optional legacy
    'WPM-Software H' address column that shifts positions). Returns dicts with
    name, addr (the WPM J/L/M address our config uses), type, rw, table
    (holding/input/coil/discrete), min, max, unit.
    """
    seen, out = set(), []
    for r in parse_html_rows(_dimplex_html()):
        rwi = next((i for i, c in enumerate(r) if (c or "").upper() in ("R", "R/W", "W")), None)
        if rwi is None:
            continue
        cr = next((c for c in r if (c or "").upper() in ("REGISTER", "REG", "COIL")), None)
        if not cr:
            continue
        nums = [c for c in r[:rwi] if re.fullmatch(r"\d{1,5}", c or "")]
        if not nums:
            continue
        addr = int(nums[0])
        typ = next((c for c in r if c and re.search(r"float|int|word", c, re.I)), "uint16")
        rw = r[rwi].upper()
        tail = r[rwi + 1:]
        tnum = [c for c in tail if re.fullmatch(r"-?\d+", c or "")]
        mn, mx = (int(tnum[0]), int(tnum[1])) if len(tnum) >= 2 else (None, None)
        unit = next((c for c in tail if c and not re.fullmatch(r"-?\d+", c) and len(c) < 8), None)
        if cr.upper() == "COIL":
            table = "coil" if rw in ("R/W", "W") else "discrete"
        else:
            table = "holding" if rw in ("R/W", "W") else "input"
        key = (table, addr)
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": r[0], "addr": addr, "type": typ, "rw": rw,
                    "table": table, "min": mn, "max": mx, "unit": unit})
    return out


if __name__ == "__main__":
    from collections import Counter
    for folder in ("pichler-lg150-lg250", "pichler-lg350-lg450"):
        sp = pichler_records(folder, "Setpoints")
        dp = pichler_records(folder, "Datapoints")
        print(f"{folder}: {len(sp)} setpoints, {len(dp)} datapoints")
    dmx = dimplex_datapoints()
    print(f"dimplex: {len(dmx)} datapoints by table {dict(Counter(d['table'] for d in dmx))}")
