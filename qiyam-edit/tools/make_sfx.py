"""Natural-style sound design (no music): whooshes on scene cuts, low thuds on the
emphatic 'no' lines, soft swishes on zoom jumps. Writes out/sfx.wav (mono 48 kHz)."""
import json, sys
import numpy as np
from scipy.signal import butter, sosfilt
import soundfile as sf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from render_overlay import SCENES, PUNCH, DUR  # noqa: E402

SR = 48000
rng = np.random.default_rng(7)
out = np.zeros(int((DUR + 1) * SR))

def put(t, y, g=1.0):
    i = int(t * SR); j = min(len(out), i + len(y))
    if i >= 0 and i < len(out): out[i:j] += g * y[: j - i]

def whoosh(dur, lo, hi, peak=.4):
    n = int(dur * SR); x = rng.standard_normal(n)
    sos = butter(2, [lo, hi], btype="band", fs=SR, output="sos"); x = sosfilt(sos, x)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return x / np.abs(x).max() * env * peak

def thud(dur=.55):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 38 + 70 * np.exp(-t * 22)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    click = sosfilt(butter(2, [120, 900], btype="band", fs=SR, output="sos"), rng.standard_normal(n)) * np.exp(-t * 60) * .25
    return (y + click) * .8

for _, a, b in SCENES:
    put(a - .04, whoosh(.42, 300, 2600, .38))
    put(b - .2, whoosh(.34, 500, 3200, .28))
for p in PUNCH:
    put(p["a"] - .02, thud(), .9)
timing = json.load(open("data/timing.json"))
for i, c in enumerate(timing):
    if i % 2 == 1 and not any(s[1] - .1 <= c["start"] <= s[2] for s in SCENES) and not any(p["a"] - .1 <= c["start"] <= p["b"] for p in PUNCH):
        put(c["start"] - .03, whoosh(.2, 700, 4200, .16))
out = np.tanh(out * 1.2) * .9
sf.write("out/sfx.wav", out.astype(np.float32), SR)
print("sfx ok", len(out) / SR)
