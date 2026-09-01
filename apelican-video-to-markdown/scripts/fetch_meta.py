#!/usr/bin/env python3
"""Dump video metadata + subtitle inventory. Never downloads audio/video."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    cookie_args,
    die,
    dump_json,
    ensure_utf8,
    find_ffmpeg,
    format_hms,
    iter_caption_tracks,
    map_ytdlp_error,
    normalize_input,
    ok,
    pick_subtitle_track,
    probe_duration,
    run_cmd,
    run_ytdlp,
    sidecar_subs,
    transcript_source_of,
    workdir_for,
    ytdlp_cmd,
)


def _local_meta(inp) -> dict:
    path = inp.path
    duration = probe_duration(path)
    tracks = []
    for sub in sidecar_subs(path):
        tracks.append({"lang": sub.suffix.lstrip("."), "automatic": False, "ext": sub.suffix.lstrip("."), "url": str(sub), "bucket": "local"})
    info = {
        "id": path.stem,
        "title": path.stem,
        "uploader": "",
        "duration": duration,
        "duration_hms": format_hms(duration),
        "tags": [],
        "webpage_url": str(path),
        "extractor": "local",
        "site": "local",
        "chapters": [],
        "subtitles": {},
        "automatic_captions": {},
        "tracks": tracks,
        "chosen_track": tracks[0] if tracks else None,
        "has_usable_subs": bool(tracks),
        "is_live": False,
        "availability": "local",
        "playlist_count": None,
        "n_entries": None,
        "playlist_index": None,
        "page": None,
        "long_video": bool(duration and duration > 20 * 60),
        "input": inp.to_dict(),
    }
    return info


def fetch_remote(inp, browser: str | None, cookies: str | None, playlist: bool) -> dict:
    prefix = ytdlp_cmd(
        [
            "--dump-json",
            "--no-download",
            "--no-warnings",
            "--skip-download",
        ]
    )
    if not playlist:
        prefix.append("--no-playlist")
    proc, cookie_source = run_ytdlp(
        prefix,
        inp.ytdlp_target(),
        timeout=120,
        browser=browser,
        cookies=cookies,
    )
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        die("E_NO_MEDIA", "yt-dlp 没有返回 JSON 元数据")
    info = json.loads(lines[0])
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        die("E_UNSUPPORTED", "正在进行的直播（未结束流）不转写")
    if info.get("_type") == "playlist" and not playlist:
        entries = info.get("entries") or []
        if entries and isinstance(entries[0], dict) and entries[0].get("id"):
            info = entries[0]
        else:
            die("E_BAD_URL", "这是播放列表。默认只处理单条；要整表请明确说「整个播放列表」")
    site = inp.site
    extractor = (info.get("extractor") or info.get("extractor_key") or "").lower()
    if "bili" in extractor:
        site = "bilibili"
    elif "youtube" in extractor:
        site = "youtube"
    tracks = iter_caption_tracks(info)
    chosen = pick_subtitle_track(info, site)
    duration = info.get("duration")
    availability = info.get("availability") or ""
    return {
        "id": info.get("id") or inp.video_id,
        "title": info.get("title") or "",
        "uploader": info.get("uploader") or info.get("channel") or info.get("creator") or "",
        "duration": duration,
        "duration_hms": format_hms(duration),
        "tags": info.get("tags") or [],
        "webpage_url": info.get("webpage_url") or inp.url,
        "extractor": info.get("extractor") or info.get("extractor_key"),
        "site": site,
        "chapters": info.get("chapters") or [],
        "description": (info.get("description") or "")[:2000],
        "subtitles": {k: v for k, v in (info.get("subtitles") or {}).items() if "danmaku" not in str(k).lower()},
        "automatic_captions": info.get("automatic_captions") or {},
        "tracks": tracks,
        "chosen_track": chosen,
        "has_usable_subs": chosen is not None,
        "transcript_source_if_subs": transcript_source_of(chosen),
        "is_live": bool(info.get("is_live")),
        "availability": availability,
        "playlist_count": info.get("playlist_count") or info.get("n_entries"),
        "n_entries": info.get("n_entries"),
        "playlist_index": info.get("playlist_index"),
        "page": inp.page,
        "long_video": bool(duration and float(duration) > 20 * 60),
        "cookie_source": cookie_source,
        "input": inp.to_dict(),
    }


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Fetch metadata + subtitle list, no media download")
    parser.add_argument("input", help="URL / BV / YouTube id / local file")
    parser.add_argument("--out", help="Write JSON to this path")
    parser.add_argument("--cookies-from-browser", dest="browser")
    parser.add_argument("--cookies")
    parser.add_argument("--playlist", action="store_true")
    args = parser.parse_args()

    if not find_ffmpeg():
        # metadata itself does not need ffmpeg, but pipeline will. Warn in payload, don't die.
        pass

    inp = normalize_input(args.input)
    if inp.kind == "local":
        data = _local_meta(inp)
    else:
        data = fetch_remote(inp, args.browser, args.cookies, args.playlist)

    out = Path(args.out) if args.out else None
    if out:
        dump_json(out, data)
        data["written"] = str(out.resolve())
    ok(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
