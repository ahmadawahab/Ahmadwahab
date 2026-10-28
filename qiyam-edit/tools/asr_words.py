"""Word-timestamp transcription with a local faster-whisper model dir.
Usage: asr_words.py MODEL_DIR SPEECH.wav OUT.json [PROMPT]"""
import json, sys
import librosa
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device="cpu", compute_type="int8")
audio, _ = librosa.load(sys.argv[2], sr=16000)
segs, info = m.transcribe(audio, language="ar", beam_size=5, word_timestamps=True,
                          condition_on_previous_text=False, vad_filter=False,
                          initial_prompt=sys.argv[4] if len(sys.argv) > 4 else None)
out = []
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text,
                "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in (s.words or [])]})
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
for s in out: print(f'{s["start"]:6.2f}-{s["end"]:6.2f} {s["text"]}')
