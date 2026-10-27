"""Renders the frame/title/captions/scenes overlay (transparent) from tools/overlay.html.

  render_overlay.py preview T1 T2 ...     -> out/prev_<T>.png on a grey backdrop
  render_overlay.py render [WORKERS]      -> out/overlay_<k>.mkv (ffv1, alpha) segments
"""
import json, subprocess, sys
from multiprocessing import Pool
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FPS, DUR = 30, 67.06
SCENES = [("road", 3.6, 5.6), ("noise", 10.7, 13.55), ("siege", 22.0, 26.35), ("coord", 32.8, 36.3),
          ("puppet1", 44.3, 47.3), ("puppet2", 50.7, 53.15), ("book", 53.6, 55.9), ("walk", 60.2, 64.1)]
PUNCH = [dict(a=39.3, b=41.45, text="لا"), dict(a=48.6, b=49.35, text="لا"),
         dict(a=58.98, b=59.95, text="لا"), dict(a=64.25, b=67.06, text="بقوة", size=360)]

def build():
    b = ROOT / "brand"
    h = (ROOT / "tools/overlay.html").read_text()
    logo = (b / "qiyam-mark-green.svg").read_text().replace('width="1024" height="1024"', 'width="124" height="124"', 1)
    rep = {"__FONT_AR800__": (b / "tajawal-arabic-800-normal.woff2").resolve().as_uri(),
           "__FONT_AR700__": (b / "tajawal-arabic-700-normal.woff2").resolve().as_uri(),
           "__FONT_LAT700__": (b / "tajawal-latin-700-normal.woff2").resolve().as_uri(),
           "__LOGO__": logo, "__DUR__": str(DUR),
           "__CHUNKS__": json.dumps(json.load(open(ROOT / "data/timing.json")), ensure_ascii=False),
           "__SCENES__": json.dumps([dict(id=i, a=a, b=c) for i, a, c in SCENES]),
           "__PUNCH__": json.dumps(PUNCH, ensure_ascii=False)}
    for k, v in rep.items():
        h = h.replace(k, v)
    out = ROOT / "out/overlay.html"
    out.write_text(h)
    return out

def open_page(p, url):
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto(url)
    pg.evaluate("document.fonts.ready")
    return b, pg

def work(args):
    k, f0, f1, url = args
    seg = ROOT / f"out/overlay_{k}.mkv"
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
                           "-c:v", "ffv1", "-pix_fmt", "yuva420p", str(seg)], stdin=subprocess.PIPE)
    with sync_playwright() as p:
        b, pg = open_page(p, url)
        for f in range(f0, f1):
            pg.evaluate(f"window.draw({f / FPS})")
            ff.stdin.write(pg.screenshot(type="png", omit_background=True))
        b.close()
    ff.stdin.close(); ff.wait()
    return str(seg)

if __name__ == "__main__":
    url = build().resolve().as_uri()
    if sys.argv[1] == "preview":
        with sync_playwright() as p:
            b, pg = open_page(p, url)
            pg.evaluate("document.body.style.background='#6b6f7a'")
            for t in sys.argv[2:]:
                pg.evaluate(f"window.draw({float(t)})")
                pg.screenshot(path=str(ROOT / f"out/prev_{t}.png"))
            b.close()
    else:
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        total = int(DUR * FPS) + 1
        per = -(-total // n)
        jobs = [(k, k * per, min(total, (k + 1) * per), url) for k in range(n)]
        with Pool(n) as pool:
            print(pool.map(work, jobs))
