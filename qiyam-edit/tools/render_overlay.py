"""Renders the frame/title/captions/scenes overlay (transparent) from tools/overlay.html.

  render_overlay.py preview T1 T2 ...     -> out/prev_<T>.png on a grey backdrop
  render_overlay.py render [WORKERS]      -> out/overlay_<k>.mkv (ffv1, alpha) segments
"""
import json, subprocess, sys
from multiprocessing import Pool
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FPS, DUR = 30, 66.6
TIMING = json.load(open(ROOT / "data/timing.json"))

def W(c, sub, k="s"):
    """time (s) of the first word of chunk c (1-based) containing `sub`"""
    for w in TIMING[c - 1]["words"]:
        if sub in w["w"]:
            return w[k]
    raise KeyError((c, sub))

def C(c, k):
    return TIMING[c - 1][k]

# scenes follow what is being said: cut in on the word, out at the end of the phrase
SCENES = [("road", W(2, "حتى") - .10, C(2, "end")), ("noise", C(5, "start") - .05, C(5, "end") + .1),
          ("siege", C(9, "start") - .05, C(10, "end")), ("coord", W(12, "يلتقي") - .10, C(12, "end")),
          ("puppet1", W(16, "وصارت") - .10, C(16, "end")), ("puppet2", W(20, "ألعوبة") - .10, C(20, "end")),
          ("book", C(21, "start") - .05, C(21, "end")), ("walk", W(24, "نملك") - .10, C(24, "end"))]
PUNCH = [dict(a=C(14, "start") - .03, b=max(C(14, "end"), C(14, "start") + .9), text="لا"),
         dict(a=C(18, "start") - .03, b=max(C(18, "end"), C(18, "start") + .9), text="لا"),
         dict(a=C(23, "start") - .03, b=max(C(23, "end"), C(23, "start") + .9), text="لا"),
         dict(a=W(25, "بقوة") - .05, b=DUR, text="بقوة", size=360)]
SCENES = [(i, round(a, 2), round(min(max(b, a + 1.0), a + 4.6), 2)) for i, a, b in SCENES]
for p in PUNCH:
    p["a"], p["b"] = round(p["a"], 2), round(p["b"], 2)
_spans = sorted([(a, b, i) for i, a, b in SCENES] + [(p["a"], p["b"], "punch") for p in PUNCH])
for (a1, b1, i1), (a2, b2, i2) in zip(_spans, _spans[1:]):
    assert b1 <= a2 + 0.01, f"overlap {i1} {b1} vs {i2} {a2}"

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
