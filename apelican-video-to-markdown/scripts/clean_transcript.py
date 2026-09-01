#!/usr/bin/env python3
"""Mechanical transcript cleanup. No invented wording."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import die, dump_json, ensure_utf8, load_json, ok

FILLERS_ZH = ("嗯", "啊", "呃", "额", "那个", "就是说", "然后呢", "咋说呢")
FILLERS_EN = ("uh", "um", "erm", "you know", "i mean")


def _norm_text(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = re.sub(r"<[^>]+>", "", t)
    return t


def _strip_filler_runs(text: str) -> str:
    t = text
    # collapse consecutive Chinese fillers
    pattern_zh = r"(?:(?:%s)[，,。.\s]*){2,}" % "|".join(map(re.escape, FILLERS_ZH))
    t = re.sub(pattern_zh, "", t)
    pattern_en = r"(?i)(?:\b(?:%s)\b[,.\s]*){2,}" % "|".join(map(re.escape, FILLERS_EN))
    t = re.sub(pattern_en, "", t)
    t = re.sub(r"\s+", " ", t).strip(" ，,。.")
    return t


def _similar(a: str, b: str) -> bool:
    a = _norm_text(a).lower()
    b = _norm_text(b).lower()
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        return len(shorter) >= 4 and len(shorter) / len(longer) >= 0.7
    return False


def clean_segments(segments: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    ordered = sorted(segments, key=lambda s: float(s.get("start") or 0))
    for raw in ordered:
        text = _strip_filler_runs(_norm_text(raw.get("text") or ""))
        if not text:
            continue
        start = float(raw.get("start") or 0)
        end = float(raw.get("end") or start)
        if end < start:
            end = start
        item = {"start": start, "end": end, "text": text}
        if cleaned:
            prev = cleaned[-1]
            gap = start - prev["end"]
            # YouTube auto-caption duplicates
            if _similar(prev["text"], text) and gap <= 2.5 and start >= prev["start"] - 0.5:
                prev["end"] = max(prev["end"], end)
                if len(text) > len(prev["text"]):
                    prev["text"] = text
                continue
            # over-fragmented cues only (YouTube 0.3s word crumbs), never glue Bcut sentences
            prev_dur = prev["end"] - prev["start"]
            cur_dur = end - start
            crumb = (len(prev["text"]) <= 8 and len(text) <= 8) and (prev_dur < 0.8 or cur_dur < 0.8)
            if crumb and gap <= 0.35 and not prev["text"].endswith(("。", "！", "？", ".", "!", "?")):
                if re.search(r"[\u4e00-\u9fff]$", prev["text"]) and re.search(r"^[\u4e00-\u9fff]", text):
                    joiner = ""
                else:
                    joiner = "" if prev["text"].endswith(("'", "-")) else " "
                prev["text"] = re.sub(r"\s+", " ", (prev["text"] + joiner + text)).strip()
                prev["end"] = max(prev["end"], end)
                continue
        cleaned.append(item)
    # drop leftover single-char filler leftovers
    out = []
    for seg in cleaned:
        if seg["text"] in FILLERS_ZH or seg["text"].lower() in FILLERS_EN:
            continue
        out.append(seg)
    return out


def load_segments(path: Path) -> tuple[list[dict], dict]:
    data = load_json(path)
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict) and "segments" in data:
        meta = {k: v for k, v in data.items() if k != "segments"}
        return data["segments"], meta
    die("E_BAD_URL", f"无法从 {path} 读取 segments")
    raise AssertionError


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Clean transcript segments")
    parser.add_argument("input")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    segs, meta = load_segments(Path(args.input))
    cleaned = clean_segments(segs)
    if not cleaned:
        die("E_NO_SPEECH", "清洗后没有对白")
    payload = {
        **meta,
        "segments": cleaned,
        "count": len(cleaned),
        "count_before": len(segs),
    }
    dump_json(Path(args.out), payload)
    ok(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
