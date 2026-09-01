#!/usr/bin/env python3
"""Download best audio only. Never muxes a video file by default."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    die,
    dump_json,
    ensure_utf8,
    ffmpeg_location,
    file_size,
    find_ffmpeg,
    format_hms,
    hint,
    need_slice,
    normalize_input,
    ok,
    probe_duration,
    run_ytdlp,
    workdir_for,
    ytdlp_cmd,
)


def already_local(inp, out_json: Path) -> dict:
    path = inp.path
    duration = probe_duration(path)
    data = {
        "audio_path": str(path),
        "duration": duration,
        "duration_hms": format_hms(duration),
        "size_bytes": file_size(path),
        "need_slice": need_slice(path, duration),
        "kept": True,
        "source": "local",
    }
    dump_json(out_json, data)
    return data


def download_audio(inp, workdir: Path, browser, cookies) -> Path:
    if not find_ffmpeg():
        die("E_FFMPEG", "抽音频需要 ffmpeg", hint("ffmpeg"))
    workdir.mkdir(parents=True, exist_ok=True)
    loc = ffmpeg_location()
    extra = [
        "-f", "ba/bestaudio",
        "-x",
        "--no-playlist",
        "--no-warnings",
        "--no-mtime",
        "-P", str(workdir),
        "-o", "%(id)s.%(ext)s",
    ]
    if loc:
        extra.extend(["--ffmpeg-location", loc])
    prefix = ytdlp_cmd(extra)
    proc, cookie_source = run_ytdlp(
        prefix,
        inp.ytdlp_target(),
        timeout=600,
        browser=browser,
        cookies=cookies,
    )
    _ = (proc, cookie_source)

    candidates = []
    for ext in (".m4a", ".webm", ".opus", ".aac", ".mp3", ".ogg", ".wav", ".flac", ".mp4"):
        candidates.extend(workdir.glob(f"*{ext}"))
    if not candidates:
        die("E_NO_MEDIA", "音频下载完成但工作目录里没有音轨文件")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Download bestaudio only")
    parser.add_argument("input")
    parser.add_argument("--workdir")
    parser.add_argument("--out", required=True, help="audio.json sidecar")
    parser.add_argument("--cookies-from-browser", dest="browser")
    parser.add_argument("--cookies")
    args = parser.parse_args()

    inp = normalize_input(args.input)
    out = Path(args.out)
    workdir = Path(args.workdir) if args.workdir else workdir_for(inp.video_id or inp.kind)

    if inp.kind == "local":
        data = already_local(inp, out)
        ok(data)
        return 0

    audio = download_audio(inp, workdir, args.browser, args.cookies)
    duration = probe_duration(audio)
    data = {
        "audio_path": str(audio.resolve()),
        "duration": duration,
        "duration_hms": format_hms(duration),
        "size_bytes": file_size(audio),
        "need_slice": need_slice(audio, duration),
        "kept": False,
        "source": "ytdlp-bestaudio",
        "workdir": str(workdir),
    }
    dump_json(out, data)
    ok(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
