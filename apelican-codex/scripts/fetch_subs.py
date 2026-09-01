#!/usr/bin/env python3
"""Download usable caption tracks only. Never treats danmaku as transcript."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    die,
    dump_json,
    ensure_utf8,
    is_danmaku_lang,
    load_json,
    normalize_input,
    ok,
    parse_subtitle_file,
    pick_subtitle_track,
    run_ytdlp,
    sidecar_subs,
    transcript_source_of,
    workdir_for,
    ytdlp_cmd,
)


def _write_segments(path: Path, segments: list, source: str, lang: str, extra: dict) -> dict:
    payload = {
        "segments": segments,
        "transcript_source": source,
        "lang": lang,
        "count": len(segments),
        **extra,
    }
    dump_json(path, payload)
    return payload


def from_local(inp, out: Path) -> dict:
    sidecars = sidecar_subs(inp.path)
    if not sidecars:
        die("E_NO_MEDIA", "本地文件没有同名字幕轨道，应走音频 + ASR")
    segs = parse_subtitle_file(sidecars[0])
    if not segs:
        die("E_NO_SPEECH", f"字幕文件解析为空: {sidecars[0]}")
    return _write_segments(out, segs, "official-cc", sidecars[0].suffix.lstrip("."), {"file": str(sidecars[0])})


def download_subs(inp, workdir: Path, browser, cookies, lang_arg: str | None, meta: dict | None) -> Path:
    langs = lang_arg
    if not langs:
        if inp.site == "bilibili":
            langs = "ai-zh,zh-Hans,zh-CN,zh.*,en.*"
        elif inp.site == "youtube":
            langs = "zh-Hans,zh-CN,zh.*,en.*,en"
        else:
            langs = "zh.*,en.*,en"

    prefix = ytdlp_cmd(
        [
            "--skip-download",
            "--no-playlist",
            "--no-warnings",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", langs,
            "--convert-subs", "srt",
            "-P", str(workdir),
            "-o", "%(id)s.%(ext)s",
        ]
    )
    run_ytdlp(
        prefix,
        inp.ytdlp_target(),
        timeout=180,
        browser=browser,
        cookies=cookies,
    )
    return workdir


def collect_sub_files(workdir: Path) -> list[Path]:
    files = []
    for ext in ("*.srt", "*.vtt", "*.json"):
        files.extend(workdir.glob(ext))
    files = [p for p in files if not is_danmaku_lang(p.name)]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def rank_file(path: Path, site: str) -> tuple:
    name = path.name.lower()
    if "danmaku" in name:
        return (99, 0)
    auto = 1 if "auto" in name or ".auto." in name else 0
    if "ai-zh" in name or "ai_zh" in name:
        return (0, auto)
    if any(k in name for k in ("zh-hans", "zh-cn", "zh.", ".zh")):
        return (1, auto)
    if ".en" in name or name.endswith(".en.srt"):
        return (3, auto)
    return (5, auto)


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Fetch caption track as segments JSON")
    parser.add_argument("input", nargs="?", help="URL / BV / local file")
    parser.add_argument("--meta", help="meta.json from fetch_meta.py")
    parser.add_argument("--workdir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cookies-from-browser", dest="browser")
    parser.add_argument("--cookies")
    parser.add_argument("--sub-langs")
    args = parser.parse_args()

    meta = load_json(Path(args.meta)) if args.meta else None
    raw_input = args.input
    if not raw_input:
        if meta and meta.get("webpage_url"):
            raw_input = meta["webpage_url"]
        else:
            die("E_BAD_URL", "需要 input 或 --meta")
    inp = normalize_input(raw_input)
    out = Path(args.out)
    workdir = Path(args.workdir) if args.workdir else workdir_for(inp.video_id or inp.kind)

    if inp.kind == "local":
        payload = from_local(inp, out)
        ok(payload)
        return 0

    if meta and not meta.get("has_usable_subs"):
        die("E_NO_MEDIA", "元数据里没有可用字幕轨道，应走 fetch_audio + ASR")

    download_subs(inp, workdir, args.browser, args.cookies, args.sub_langs, meta)
    files = collect_sub_files(workdir)
    if not files:
        die("E_NO_MEDIA", "字幕下载后工作目录里没有 srt/vtt。可能要 Cookie（B站 ai-zh）")

    files.sort(key=lambda p: rank_file(p, inp.site))
    chosen = files[0]
    segs = parse_subtitle_file(chosen)
    if not segs:
        die("E_NO_SPEECH", f"字幕解析为空: {chosen.name}")

    track = None
    if meta:
        track = meta.get("chosen_track")
    source = transcript_source_of(track)
    if "ai-zh" in chosen.name.lower():
        source = "official-ai-sub"
    elif "auto" in chosen.name.lower():
        source = "yt-auto-sub"
    payload = _write_segments(
        out,
        segs,
        source,
        chosen.stem,
        {"file": str(chosen), "workdir": str(workdir)},
    )
    ok(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
