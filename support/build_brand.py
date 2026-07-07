"""Regenerate the Modbus Connect brand assets (SVGs here, PNGs in brand/).

The mark is a Modbus network in the Home Assistant logo style: the brand blue
tile (#18BCF2), off-white traces (#F2F4F9), one bus trunk, the gateway node on
top and two device nodes below. The wordmark is outlined from Figtree (the
Home Assistant brand typeface, OFL) so the SVGs are fully self-contained.

Usage:
    curl -sL -o figtree.ttf \
        "https://github.com/google/fonts/raw/main/ofl/figtree/Figtree%5Bwght%5D.ttf"
    pip install fonttools
    python3 support/build_brand.py figtree.ttf

PNG rendering (needs rsvg-convert and imagemagick):
    cd support
    B=../custom_components/modbus_connect/brand
    rsvg-convert -w 256  -h 256 icon.svg      -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/icon.png
    rsvg-convert -w 512  -h 512 icon.svg      -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/icon@2x.png
    rsvg-convert -h 128         logo.svg      -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/logo.png
    rsvg-convert -w 1498 -h 256 logo.svg      -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/logo@2x.png
    rsvg-convert -h 128         logo-dark.svg -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/dark_logo.png
    rsvg-convert -w 1498 -h 256 logo-dark.svg -o /tmp/x.png && magick /tmp/x.png -strip -interlace PNG $B/dark_logo@2x.png
"""

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(__file__).parent

BLUE = "#18BCF2"  # Home Assistant brand blue
TRACE = "#F2F4F9"  # Home Assistant trace white
DARK = "#1D2126"  # Home Assistant wordmark color

TEXT = "Modbus Connect"
WEIGHT = 600
CAP = 26.0  # wordmark cap height in icon units (icon is 64 x 64)
BASELINE = 45.0  # wordmark baseline y
TEXT_X = 79.0  # wordmark start x
TRACKING = 0.008  # letter spacing, in em


def outline_text(font_path: Path) -> tuple[str, float]:
    """Return (SVG path elements, end x) for TEXT, drawn on the logo grid."""
    font = TTFont(font_path)
    instantiateVariableFont(font, {"wght": WEIGHT}, inplace=True)
    upm = font["head"].unitsPerEm
    cap_height = font["OS/2"].sCapHeight or int(upm * 0.7)
    scale = CAP / cap_height
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()

    parts: list[str] = []
    x = TEXT_X
    for char in TEXT:
        if char == " ":
            x += glyph_set[cmap[ord(" ")]].width * scale
            continue
        glyph = glyph_set[cmap[ord(char)]]
        pen = SVGPathPen(glyph_set)
        glyph.draw(pen)
        if d := pen.getCommands():
            parts.append(
                f'<path transform="translate({x:.2f} {BASELINE}) '
                f'scale({scale:.6f} -{scale:.6f})" d="{d}"/>'
            )
        x += glyph.width * scale + TRACKING * upm * scale
    return "\n    ".join(parts), x - TRACKING * upm * scale


MARK = f"""<rect width="64" height="64" rx="14.5" fill="{BLUE}"/>
  <g fill="none" stroke="{TRACE}" stroke-width="5" stroke-linecap="round">
    <path d="M12 35h40"/>
    <path d="M32 35V21"/>
    <path d="M20 35v9"/>
    <path d="M44 35v9"/>
  </g>
  <g fill="{TRACE}">
    <circle cx="32" cy="15" r="7.5"/>
    <circle cx="20" cy="48.5" r="6"/>
    <circle cx="44" cy="48.5" r="6"/>
  </g>"""


def icon_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <title>Modbus Connect</title>
  {MARK}
</svg>
"""


def logo_svg(font_path: Path, text_color: str) -> str:
    text_paths, end_x = outline_text(font_path)
    width = round(end_x + 1.5, 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 64">
  <title>Modbus Connect</title>
  {MARK}
  <g fill="{text_color}">
    {text_paths}
  </g>
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_brand.py <path to Figtree[wght].ttf> — see module docstring")
    font = Path(sys.argv[1])
    if not font.is_file():
        sys.exit(f"font file not found: {font}")
    (OUT / "icon.svg").write_text(icon_svg(), encoding="utf-8")
    (OUT / "logo.svg").write_text(logo_svg(font, DARK), encoding="utf-8")
    (OUT / "logo-dark.svg").write_text(logo_svg(font, TRACE), encoding="utf-8")
    print("written:", *(p.name for p in sorted(OUT.glob("*.svg"))))
