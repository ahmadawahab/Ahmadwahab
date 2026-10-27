"""Composites source video + overlay segments + sfx into the final cut.
Usage: build_video.py OUT.mp4 SOURCE.mp4   (run render_overlay.py render + make_sfx.py first)
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out, src = sys.argv[1], sys.argv[2]
sys.path.insert(0, str(ROOT / "tools"))
from render_overlay import SCENES, DUR  # noqa: E402

T = json.load(open(ROOT / "data/timing.json"))
terms = []
for i, c in enumerate(T):
    a = 0.0 if i == 0 else c["start"]
    b = T[i + 1]["start"] if i + 1 < len(T) else DUR + 1
    if c.get("punch"): z0, dz = 1.34, .05
    elif i % 2 == 0: z0, dz = 1.06, .05
    else: z0, dz = 1.22, .05
    terms.append(f"between(t,{a:.3f},{b:.3f})*({z0}+{dz}*(t-{a:.3f})/{max(b - a, .1):.3f})")
Z = "(" + "+".join(terms) + ")"
gate = "+".join(f"between(t,{a + .15:.2f},{b + .02:.2f})" for _, a, b in SCENES)

fg = f"""
color=c=0x0F1630:s=1080x1920:r=30:d={DUR}[base];
[0:v]scale=w='trunc(576*1.66*{Z}/2)*2':h='trunc(1024*1.66*{Z}/2)*2':eval=frame:flags=bicubic,
 crop=870:990:x='clip(300*iw/576-435,10*iw/576,505*iw/576-870)':y='clip(480*ih/1024-470,12*ih/1024,ih-990)',
 eq=contrast=1.07:saturation=1.05,vignette=PI/6,noise=alls=3:allf=t,format=yuv420p,setsar=1[win];
[0:v]crop=360:360:130:250,scale=280:280,setsar=1[pip];
[base][win]overlay=40:200:shortest=1[b1];
[b1][pip]overlay=65:885:enable='{gate}'[b2];
[b2][2:v]overlay=0:0:format=auto,format=yuv420p[v];
[0:a]highpass=f=75,loudnorm=I=-16:TP=-1.5:LRA=7[sp];
[1:a]volume=0.55[fx];
[sp][fx]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95,
 afade=t=out:st={DUR - 0.4}:d=0.4,aresample=48000,aformat=channel_layouts=stereo[a]
"""
(ROOT / "out/filter.txt").write_text(fg)
segs = sorted((ROOT / "out").glob("overlay_*.mkv"), key=lambda p: int(p.stem.split("_")[1]))
(ROOT / "out/segs.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in segs))
main = ROOT / "out/gaza_main.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", str(ROOT / "out/sfx.wav"),
                "-f", "concat", "-safe", "0", "-i", str(ROOT / "out/segs.txt"),
                "-filter_complex_script", str(ROOT / "out/filter.txt"), "-map", "[v]", "-map", "[a]",
                "-t", str(DUR), "-c:v", "libx264", "-crf", "21", "-maxrate", "8M", "-bufsize", "16M", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", str(main)], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(main), "-i", str(ROOT / "out/outro.mp4"),
                "-f", "lavfi", "-t", "3.4", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex",
                "[0:v]setsar=1[v0];[1:v]setsar=1[v1];[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "21", "-maxrate", "8M", "-bufsize", "16M",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
print("done", out)
