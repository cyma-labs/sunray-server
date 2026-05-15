#!/usr/bin/env python3
"""Generate Sunray addon icons and backend favicon from the master logo.

Reads /opt/muppy/workspace-sunray/logos/logo_sunray.png and writes:
  - 256x256 RGBA icon.png in each Sunray-related addon's static/description/
  - multi-resolution favicon.ico (16/32/48) under sunray_core/static/src/img/

Idempotent. Re-run any time the master logo changes.

Usage:
    appserver-sunray18/py3x/bin/python3 \
        appserver-sunray18/bin/generate_branding_icons.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path("/opt/muppy/workspace-sunray")
SRC = ROOT / "logos" / "logo_sunray.png"

ICON_TARGETS = [
    ROOT / "appserver-sunray18/project_addons/sunray_core/static/description/icon.png",
    ROOT / "appserver-sunray18/project_addons/inouk_cloudflare_longpolling_patch/static/description/icon.png",
    ROOT / "appserver-sunray18/project_addons_advanced/sunray_advanced_core/static/description/icon.png",
    ROOT / "appserver-sunray18/project_addons_advanced/sunray_dashboard/static/description/icon.png",
]
FAVICON = ROOT / "appserver-sunray18/project_addons/sunray_core/static/src/img/favicon.ico"

ICON_SIZE = 256
FAVICON_SIZES = [(16, 16), (32, 32), (48, 48)]


def square_canvas(img: Image.Image) -> Image.Image:
    """Pad to a square transparent canvas if not already square."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    if w == h:
        return img
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
    return canvas


def main() -> None:
    master = Image.open(SRC)
    sq = square_canvas(master)

    icon = sq.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    for target in ICON_TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        icon.save(target, format="PNG", optimize=True)
        print(f"wrote {target}")

    FAVICON.parent.mkdir(parents=True, exist_ok=True)
    sq.save(FAVICON, format="ICO", sizes=FAVICON_SIZES)
    print(f"wrote {FAVICON}")


if __name__ == "__main__":
    main()
