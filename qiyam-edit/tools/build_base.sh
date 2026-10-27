#!/bin/bash
# Base cut: crop out the source account's edge mark, 1080x1920, light grade + grain,
# Qiyam mark top-left, loudness-normalised audio, then the outro.
# Usage: build_base.sh SOURCE.mp4 OUT.mp4
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="$1"; OUT="$2"
python3 -I tools/svg_to_png.py brand/qiyam-mark-green.svg out/mark.png 132
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC")
ffmpeg -v error -y -i "$SRC" -i out/mark.png -filter_complex "
[0:v]crop=524:932:10:12,scale=1080:1920:flags=lanczos,setsar=1,
 eq=contrast=1.06:saturation=1.04,vignette=PI/6,noise=alls=3:allf=t[v];
[v][1:v]overlay=48:64[main]" \
 -map "[main]" -map 0:a -af "highpass=f=75,loudnorm=I=-15:TP=-1.5:LRA=7,afade=t=out:st=$(python3 -c "print(max(0,$DUR-0.4))"):d=0.4" \
 -c:v libx264 -crf 21 -maxrate 8M -bufsize 16M -preset medium -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k out/main.mp4
ffmpeg -v error -y -i out/main.mp4 -i out/outro.mp4 -f lavfi -t 3.4 -i anullsrc=r=48000:cl=stereo -filter_complex \
 "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[0:v][a0][1:v][2:a]concat=n=2:v=1:a=1[v][a]" \
 -map "[v]" -map "[a]" -c:v libx264 -crf 21 -maxrate 8M -bufsize 16M -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$OUT"
