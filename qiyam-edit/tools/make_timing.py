"""Builds data/timing.json from data/script.json and the speech track.

Estimate only (no speech recogniser is reachable from this environment): script
syllables are aligned to syllable nuclei detected in the audio with a monotonic DP,
run under several detector/cost settings; each chunk takes the median. `spread`
(seconds) is the disagreement between runs: large spread = low confidence.

Usage: make_timing.py SPEECH.wav
"""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np, librosa
from scipy.signal import butter, sosfiltfilt, find_peaks

ROOT = Path(__file__).resolve().parent.parent
chunks = json.load(open(ROOT / "data/script.json"))

def syl(s):
    p = subprocess.run(["espeak-ng", "-v", "ar", "-q", "--ipa", s], capture_output=True, text=True).stdout
    return len(re.findall(r"[aiuəɪʊɐeoæɑɔ]ː?", p)) or 1

S = [syl(c["ar"]) for c in chunks]
bstr = []
for c, n in zip(chunks, S):
    bstr += [0] * (n - 1) + [2 if c.get("end") else 1]
M = len(bstr)

y, _ = librosa.load(sys.argv[1], sr=16000)
band = sosfiltfilt(butter(4, [300, 3000], btype="band", fs=16000, output="sos"), y)

def detect(prom, dist, pct, lowhz):
    hop = 80
    env = np.sqrt(np.convolve(band ** 2, np.ones(hop * 4) / (hop * 4), mode="same"))[::hop]
    sm = sosfiltfilt(butter(2, lowhz, btype="low", fs=200, output="sos"), librosa.amplitude_to_db(env + 1e-6))
    pk, _ = find_peaks(sm, distance=int(dist * 200), prominence=prom)
    return pk[sm[pk] > np.percentile(sm, pct)] / 200.0

def align(t, alpha, gam):
    N = len(t); pause = np.clip(np.append(np.diff(t), 5.0) - 0.30, 0, 1.5)
    D = np.full((M + 1, N + 1), 1e9); B = np.zeros((M + 1, N + 1), dtype=np.int8)
    D[0, :] = np.arange(N + 1) * gam * 0.15; D[:, 0] = np.arange(M + 1) * gam
    for i in range(1, M + 1):
        bi = bstr[i - 1]
        for j in range(1, N + 1):
            if bi == 0: c = alpha * pause[j - 1]
            else:
                need = 0.45 if bi == 1 else 0.9
                c = (0.9 if bi == 2 else 0.45) * max(0.0, 1 - pause[j - 1] / need)
            m = D[i - 1, j - 1] + c; st = D[i - 1, j] + gam; sn = D[i, j - 1] + (gam * 0.15 if i == M else gam)
            if m <= st and m <= sn: D[i, j], B[i, j] = m, 0
            elif st <= sn: D[i, j], B[i, j] = st, 1
            else: D[i, j], B[i, j] = sn, 2
    i, j = M, N; mt = {}
    while i > 0 and j > 0:
        b = B[i, j]
        if b == 0: mt[i - 1] = j - 1; i -= 1; j -= 1
        elif b == 1: i -= 1
        else: j -= 1
    tm = np.full(M, np.nan)
    for k, v in mt.items(): tm[k] = t[v]
    idx = np.arange(M); ok = ~np.isnan(tm)
    return np.interp(idx, idx[ok], tm[ok])

SETTINGS = [(2.5, .11, 35, 10, .5, .9), (2.0, .10, 35, 10, .5, .9), (3.0, .12, 35, 10, .5, .9), (2.5, .11, 30, 12, .5, .9),
            (2.5, .11, 35, 10, .9, .9), (2.5, .11, 35, 10, .3, .6), (2.5, .11, 40, 8, .5, 1.2)]
first, last = [], []
for prom, dist, pct, lh, alpha, gam in SETTINGS:
    tm = align(detect(prom, dist, pct, lh), alpha, gam)
    p = 0; a = []; b = []
    for n in S:
        a.append(tm[p]); b.append(tm[p + n - 1]); p += n
    first.append(a); last.append(b)
first, last = np.array(first), np.array(last)
start = np.maximum.accumulate(np.median(first, 0) - 0.10).clip(0)
end = np.median(last, 0) + 0.18
spread = first.max(0) - first.min(0)

out = [{**c, "syl": n, "start": round(float(a), 2), "end": round(float(max(b, a + .3)), 2), "spread": round(float(s), 2)}
       for c, n, a, b, s in zip(chunks, S, start, end, spread)]
json.dump(out, open(ROOT / "data/timing.json", "w"), ensure_ascii=False, indent=1)
for k, o in enumerate(out, 1):
    flag = "  <-- low confidence" if o["spread"] > 0.8 else ""
    print(f'{k:2d} {o["start"]:6.2f} {o["end"]:6.2f} spread={o["spread"]:.2f}  {o["ar"][:28]}{flag}')
