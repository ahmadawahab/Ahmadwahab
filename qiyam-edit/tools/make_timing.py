"""Builds data/timing.json from data/script.json.

No speech recogniser was available, so times are ESTIMATES: chunks are anchored
to the pauses measured in the audio (silence/energy dips) and spread between
anchors in proportion to their syllable counts. Review against the audio and
edit data/anchors.json (chunk number -> seconds) to correct any drift.
"""
import json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
chunks = json.load(open(ROOT / "data/script.json"))
cfg = json.load(open(ROOT / "data/anchors.json"))
pauses = [tuple(p) for p in cfg["pauses"]]
starts = {int(k): v for k, v in cfg["starts"].items()}
ends = {int(k): v for k, v in cfg["ends"].items()}
MIN = {True: 0.9, False: 0.6}

def syl(s):
    p = subprocess.run(["espeak-ng", "-v", "ar", "-q", "--ipa", s], capture_output=True, text=True).stdout
    return len(re.findall(r"[aiuəɪʊɐeoæɑɔ]ː?", p)) or 1

S = [syl(c["ar"]) for c in chunks]
n = len(chunks)
T = [None] * n  # [start, end]

def span_speech(a, b):
    """speech seconds between a and b, pauses removed"""
    return (b - a) - sum(max(0, min(b, y) - max(a, x)) for x, y in pauses)

def advance(t, dur):
    """real time reached after `dur` speech seconds starting at t"""
    for x, y in sorted(pauses):
        if y <= t: continue
        if x <= t < y: t = y
        room = x - t
        if dur <= room or x < t: break
        dur -= room; t = y
    return t + dur

# group consecutive chunks into spans delimited by known starts/ends
i = 0
while i < n:
    a = starts.get(i + 1, 0.0 if i == 0 else None)
    if a is None:
        a = T[i - 1][1] if i and T[i - 1] else None
    j = i
    while j < n and (j + 1) not in ends and (j + 1 >= n or (j + 2) not in starts):
        j += 1
    b = ends.get(j + 1) if j < n else None
    if b is None:
        b = starts.get(j + 2) if j + 1 < n else cfg["speech_end"]
    group = list(range(i, min(j, n - 1) + 1))
    total = sum(max(S[k], 1) for k in group)
    speech = span_speech(a, b)
    t = a
    for k in group:
        d = speech * S[k] / total
        d = max(d, MIN[bool(chunks[k].get("punch"))]) if len(group) > 1 else d
        e = advance(t, d)
        T[k] = [t, min(e, b)]
        t = e if k != group[-1] else b
        if k != group[-1]:
            nxt = starts.get(k + 2)
            t = nxt if nxt is not None and nxt >= e - 0.05 else t
    T[group[-1]][1] = b
    i = group[-1] + 1

out = [{**c, "start": round(t[0], 2), "end": round(t[1], 2), "syl": s} for c, t, s in zip(chunks, T, S)]
json.dump(out, open(ROOT / "data/timing.json", "w"), ensure_ascii=False, indent=1)
for k, o in enumerate(out, 1):
    print(f'{k:2d} {o["start"]:6.2f} {o["end"]:6.2f}  {o["ar"][:34]}')
