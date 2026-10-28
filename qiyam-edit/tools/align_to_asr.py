"""Aligns the approved script to what a local Whisper pass heard, at character level,
so every chunk/word gets real start/end times while captions keep the approved text.

Usage: align_to_asr.py SPEECH.wav ASR.json [ASR2.json ...]   (several runs are averaged)
Writes data/timing.json (chunks with start/end/spread and per-word times).
"""
import json, re, sys
from difflib import SequenceMatcher
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
chunks = json.load(open(ROOT / "data/script.json"))

def norm(w):
    w = re.sub(r"[ً-ٰٟـ،؟؛,.!?:\-—«»]", "", w)
    w = re.sub("[أإآٱ]", "ا", w).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    return w

# script characters -> (chunk, word)
s_chars, s_chunk, s_word = [], [], []
words = []                                   # (chunk, word text)
for ci, c in enumerate(chunks):
    for w in c["ar"].split():
        wi = len(words); words.append((ci, w))
        for ch in norm(w):
            s_chars.append(ch); s_chunk.append(ci); s_word.append(wi)
S = "".join(s_chars)

SIMILAR = ["تط", "دض", "سصث", "ذزظ", "هح", "كق", "عا", "غخ", "نم", "يا", "وا", "لر"]
def pair_score(a, b):
    if a == b: return 2.0
    if any(a in g and b in g for g in SIMILAR): return 0.0
    return -1.2

def char_times(asr_path):
    asr = json.load(open(asr_path))
    a_chars, a_t = [], []
    for seg in asr:
        for x in seg["words"]:
            w = norm(x["w"].strip())
            for k, ch in enumerate(w):
                a_chars.append(ch); a_t.append(x["s"] + (x["e"] - x["s"]) * (k + .5) / max(len(w), 1))
    A = "".join(a_chars); n, m = len(S), len(A); GAP = -1.0
    D = np.zeros((n + 1, m + 1)); Tb = np.zeros((n + 1, m + 1), dtype=np.int8)
    D[:, 0] = np.arange(n + 1) * GAP; D[0, :] = np.arange(m + 1) * GAP; Tb[1:, 0] = 1; Tb[0, 1:] = 2
    sc = np.array([[pair_score(a, b) for b in A] for a in S])
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = D[i - 1, j - 1] + sc[i - 1, j - 1]; u = D[i - 1, j] + GAP; l = D[i, j - 1] + GAP
            if d >= u and d >= l: D[i, j], Tb[i, j] = d, 0
            elif u >= l: D[i, j], Tb[i, j] = u, 1
            else: D[i, j], Tb[i, j] = l, 2
    i, j = n, m; t = np.full(n, np.nan); matched = 0
    while i > 0 and j > 0:
        b = Tb[i, j]
        if b == 0:
            if sc[i - 1, j - 1] > 0: t[i - 1] = a_t[j - 1]; matched += 1
            i -= 1; j -= 1
        elif b == 1: i -= 1
        else: j -= 1
    idx = np.arange(n); ok = ~np.isnan(t)
    return np.interp(idx, idx[ok], t[ok]), matched / n, ok

AUDIO = sys.argv[1]
runs = [char_times(p) for p in sys.argv[2:]]
print("matched script characters per run:", [round(float(r[1]), 2) for r in runs])
T = np.mean([r[0] for r in runs], 0)
spread = (np.max([r[0] for r in runs], 0) - np.min([r[0] for r in runs], 0)) if len(runs) > 1 else np.zeros(len(S))
s_chunk = np.array(s_chunk); s_word = np.array(s_word)

out = []
for ci, c in enumerate(chunks):
    m = s_chunk == ci
    a, b = float(T[m].min()), float(T[m].max())
    ws = []
    for wi, (wc, w) in enumerate(words):
        if wc != ci: continue
        mw = s_word == wi
        ws.append({"w": w, "s": round(float(T[mw].min()), 2), "e": round(float(T[mw].max()), 2)})
    out.append({**c, "start": round(a - 0.08, 2), "end": round(b + 0.16, 2), "spread": round(float(spread[m].max()), 2), "words": ws})
# Whisper stretches segment edges across silence: snap chunk edges to the measured pauses
import librosa
y, _ = librosa.load(AUDIO, sr=16000); hop = 400
db = 20 * np.log10(np.array([np.sqrt(np.mean(y[k * hop:(k + 1) * hop] ** 2)) + 1e-9 for k in range(len(y) // hop)]))
low = db < np.percentile(db, 18); pauses = []; k = 0
while k < len(low):
    if low[k]:
        e = k
        while e < len(low) and low[e]: e += 1
        if (e - k) * 0.025 >= 0.15: pauses.append((k * 0.025, e * 0.025))
        k = e
    else: k += 1
for o in out:
    for ps, pe in pauses:
        if ps - 0.40 <= o["start"] <= pe + 0.15: o["start"] = round(max(o["start"], pe - 0.04), 2)
        if ps - 0.12 <= o["end"] <= pe + 0.05: o["end"] = round(min(o["end"], ps + 0.10), 2)
print("pauses used for snapping:", [(round(a, 2), round(b, 2)) for a, b in pauses])
for i in range(1, len(out)):                  # keep chunks ordered
    if out[i]["start"] < out[i - 1]["start"] + 0.1: out[i]["start"] = round(out[i - 1]["start"] + 0.1, 2)
for o in out: o["end"] = round(max(o["end"], o["start"] + 0.35), 2)
json.dump(out, open(ROOT / "data/timing.json", "w"), ensure_ascii=False, indent=1)
for i, o in enumerate(out, 1):
    print(f'{i:2d} {o["start"]:6.2f} {o["end"]:6.2f}  {o["ar"][:34]}')
