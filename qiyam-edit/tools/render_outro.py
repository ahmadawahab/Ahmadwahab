"""Renders the Qiyam outro (original animated logo + signature) to an MP4.

The logo is the original brand SVG, scrubbed with SMIL setCurrentTime so its
own keyframes drive the animation. Usage: render_outro.py OUT.mp4
"""
import asyncio
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, DUR = 1080, 1920, 30, 3.4
LOGO_AT, TEXT_AT = 0.0, 1.9  # seconds

logo_svg = (ROOT / "brand/qiyam-logo-animated.svg").read_text()
logo_svg = logo_svg.replace('width="1024" height="1024"', 'width="620" height="620" id="logo"', 1)
font = (ROOT / "brand/tajawal-arabic-800-normal.woff2").resolve().as_uri()

HTML = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:T;src:url({font});font-weight:800}}
html,body{{margin:0;width:{W}px;height:{H}px;background:#0F1630;overflow:hidden}}
#logo{{position:absolute;left:{(W-620)//2}px;top:640px}}
#sig{{position:absolute;left:0;right:0;top:1300px;text-align:center;direction:rtl;
 font:800 84px/1.3 T,sans-serif;color:#FFF7E8;opacity:0}}
#sig b{{color:#FFC93C;font-weight:800}}
</style></head><body>{logo_svg}
<div id="sig">قيم… <b>نهتدي بها</b></div></body></html>"""


async def main(out: str) -> None:
    ff = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
         "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", out],
        stdin=subprocess.PIPE)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page(viewport={"width": W, "height": H})
        await pg.set_content(HTML)
        await pg.evaluate("document.fonts.ready")
        await pg.evaluate("document.getElementById('logo').pauseAnimations()")
        for i in range(int(DUR * FPS)):
            t = i / FPS
            k = min(1, max(0, (t - TEXT_AT) / 0.6))
            await pg.evaluate(
                "([t,k])=>{document.getElementById('logo').setCurrentTime(Math.min(t,2.3));"
                "const s=document.getElementById('sig');s.style.opacity=k;"
                "s.style.transform=`translateY(${(1-k)*24}px)`}", [t, k])
            ff.stdin.write(await pg.screenshot(type="jpeg", quality=94))
        await b.close()
    ff.stdin.close()
    ff.wait()


asyncio.run(main(sys.argv[1]))
