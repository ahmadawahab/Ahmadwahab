"""Rasterises a brand SVG to a transparent PNG. Usage: svg_to_png.py IN.svg OUT.png SIZE"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

src, out, size = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
svg = src.read_text().replace('width="1024" height="1024"', f'width="{size}" height="{size}"', 1)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": size, "height": size})
    pg.set_content(f"<body style='margin:0;background:transparent'>{svg}</body>")
    pg.screenshot(path=out, omit_background=True)
    b.close()
