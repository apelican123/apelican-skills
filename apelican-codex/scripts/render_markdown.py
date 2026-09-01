#!/usr/bin/env python3
"""Render Markdown from meta + cleaned segments + agent-provided summary/body."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    dated_markdown_name,
    die,
    ensure_utf8,
    format_hms,
    load_json,
    now_iso,
    ok,
    safe_filename,
)

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"

MODE_TEMPLATE = {
    "default": "default.md",
    "full": "full-transcript.md",
    "notes": "notes.md",
    "summary": "default.md",
    "obsidian": "obsidian.md",
}


def ts_bracket(seconds: float) -> str:
    return f"`[{format_hms(seconds)}]`"


def raw_transcript(segments: list[dict], timestamps: bool = True) -> str:
    lines = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if timestamps:
            lines.append(f"{ts_bracket(float(seg['start']))} {text}")
        else:
            lines.append(text)
    return "\n\n".join(lines)


def yaml_list(items: list[str]) -> str:
    if not items:
        return "  - video-transcript"
    return "\n".join(f"  - {it}" for it in items)


def md_bullets(items: list[str]) -> str:
    return "\n".join(f"- {it}" for it in items) if items else "- （无）"


def fill(template: str, mapping: dict[str, str]) -> str:
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value if value is not None else "")
    leftover = re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", out)
    for token in leftover:
        out = out.replace(token, "")
    return out


def mechanical_body(segments: list[dict], chapters: list | None, timestamps: bool) -> str:
    if chapters:
        parts = []
        for ch in chapters:
            title = (ch.get("title") or "").strip() or "未命名段落"
            start = float(ch.get("start_time") or ch.get("start") or 0)
            stamp = f" {ts_bracket(start)}" if timestamps else ""
            parts.append(f"### {title}{stamp}\n")
            end = ch.get("end_time") or ch.get("end")
            chunk = []
            for seg in segments:
                if float(seg["start"]) < start - 0.2:
                    continue
                if end is not None and float(seg["start"]) >= float(end):
                    break
                chunk.append(seg["text"])
            parts.append("".join(f"{t}" if t.endswith(("。", "！", "？")) else t + " " for t in chunk).strip())
            parts.append("")
        return "\n".join(parts).strip()
    # fallback: pack ~90s windows, title from first 12 chars
    if not segments:
        return ""
    parts = []
    window = []
    win_start = float(segments[0]["start"])
    for seg in segments:
        if window and float(seg["start"]) - win_start >= 90:
            title = window[0]["text"][:18].rstrip("，,。 ")
            stamp = f" {ts_bracket(win_start)}" if timestamps else ""
            parts.append(f"### {title}{stamp}\n")
            parts.append(" ".join(s["text"] for s in window))
            parts.append("")
            window = []
            win_start = float(seg["start"])
        window.append(seg)
    if window:
        title = window[0]["text"][:18].rstrip("，,。 ")
        stamp = f" {ts_bracket(win_start)}" if timestamps else ""
        parts.append(f"### {title}{stamp}\n")
        parts.append(" ".join(s["text"] for s in window))
    return "\n".join(parts).strip()


def read_maybe(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return path.strip()


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Render markdown from transcript artifacts")
    parser.add_argument("--meta", required=True)
    parser.add_argument("--segments", required=True)
    parser.add_argument("--mode", default="default", choices=list(MODE_TEMPLATE))
    parser.add_argument("--transcript-source", dest="source", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--timestamps", default="on", choices=["on", "off"])
    parser.add_argument("--no-raw", action="store_true", help="Omit original transcript appendix")
    parser.add_argument("--language", default="")
    parser.add_argument("--out-dir", default="transcripts")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    meta = load_json(Path(args.meta))
    seg_blob = load_json(Path(args.segments))
    segments = seg_blob.get("segments") if isinstance(seg_blob, dict) else seg_blob
    if not isinstance(segments, list):
        die("E_BAD_URL", "segments 文件格式不对")

    source = args.source or (seg_blob.get("transcript_source") if isinstance(seg_blob, dict) else "") or meta.get("transcript_source_if_subs") or "unknown"
    timestamps = args.timestamps == "on"
    mode = args.mode
    include_raw = mode not in {"summary", "notes"} and not (mode == "obsidian" and not args.body)
    if mode == "notes":
        include_raw = False
    if mode == "summary":
        include_raw = False
    if mode == "full":
        include_raw = True
    if args.no_raw:
        include_raw = False

    summary = read_maybe(args.summary)
    body = read_maybe(args.body)
    if not body:
        body = mechanical_body(segments, meta.get("chapters") or [], timestamps)
    if not summary:
        joined = "".join(s.get("text") or "" for s in segments)
        summary = joined[:220] + ("…" if len(joined) > 220 else "")
        if mode != "full":
            summary = summary or "（脚本未收到摘要；Agent 应基于转写重写 120–250 字，不得编造。）"

    keywords = [k.strip() for k in re.split(r"[,，\n]", args.keywords) if k.strip()]
    if not keywords:
        keywords = list(meta.get("tags") or [])[:8]
        keywords = [str(k) for k in keywords]

    title = meta.get("title") or "untitled"
    site = meta.get("site") or "other"
    vid = str(meta.get("id") or "video")
    url = meta.get("webpage_url") or ""
    author = meta.get("uploader") or ""
    duration = format_hms(meta.get("duration"))
    language = args.language or (seg_blob.get("lang") if isinstance(seg_blob, dict) else "") or "zh"
    created = now_iso()
    filename = dated_markdown_name(title)
    out_path = Path(args.out) if args.out else Path(args.out_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tags = ["video-transcript", site]
    raw = raw_transcript(segments, timestamps=timestamps) if include_raw else ""
    if mode == "summary":
        raw = ""
    short_title = safe_filename(title, 24)

    tpl_name = MODE_TEMPLATE[mode]
    tpl_path = TEMPLATE_DIR / tpl_name
    if not tpl_path.exists():
        die("E_BAD_URL", f"缺少模板 {tpl_path}")
    mapping = {
        "title": title,
        "url": url,
        "site": site,
        "author": author,
        "duration": duration,
        "language": language,
        "transcript_source": source,
        "created": created,
        "tags_yaml": yaml_list(tags),
        "summary": summary,
        "main_content": body,
        "keywords_md": md_bullets(keywords),
        "raw_transcript": raw,
        "aliases": short_title,
        "short_title": short_title,
        "id": vid,
    }
    text = fill(tpl_path.read_text(encoding="utf-8"), mapping)
    if not include_raw:
        text = re.sub(r"\n## 原始转写[\s\S]*$", "\n", text).rstrip() + "\n"
    out_path.write_text(text, encoding="utf-8")
    payload = {
        "path": str(out_path.resolve()),
        "title": title,
        "mode": mode,
        "transcript_source": source,
        "bytes": out_path.stat().st_size,
    }
    ok(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
