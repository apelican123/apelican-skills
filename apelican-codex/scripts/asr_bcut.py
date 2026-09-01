#!/usr/bin/env python3
"""
Cloud Bcut ASR (default engine).

Protocol follows the community MIT client SocialSisterYi/bcut-asr
(https://github.com/SocialSisterYi/bcut-asr) against
https://member.bilibili.com/x/bcut/rubick-interface

This is NOT an official Bilibili API. No SLA. Audio is uploaded to Bilibili.
Private / internal content should use asr_whisper.py instead.

Public API:
    transcribe(audio_path) -> list[{start, end, text}]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    convert_for_bcut,
    die,
    dump_json,
    ensure_utf8,
    file_size,
    format_hms,
    merge_sliced_segments,
    need_slice,
    ok,
    probe_duration,
    slice_audio,
    workdir_for,
)

API_BASE = "https://member.bilibili.com/x/bcut/rubick-interface"
API_REQ_UPLOAD = API_BASE + "/resource/create"
API_COMMIT_UPLOAD = API_BASE + "/resource/create/complete"
API_CREATE_TASK = API_BASE + "/task"
API_QUERY_RESULT = API_BASE + "/task/result"
MODEL_ID = 7
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


class BcutError(Exception):
    def __init__(self, message: str, code: str = "E_BCUT") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _request(url: str, *, method: str = "GET", data: Optional[bytes] = None, headers: Optional[dict] = None, timeout: int = 60):
    hdrs = {
        "User-Agent": UA,
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com",
    }
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except HTTPError as exc:
        body = exc.read() if exc.fp else b""
        raise BcutError(f"HTTP {exc.code} {url}: {body[:300]!r}") from exc
    except URLError as exc:
        raise BcutError(f"网络错误: {exc.reason}") from exc


def _json_post_form(url: str, fields: dict) -> dict:
    payload = urlencode(fields).encode("utf-8")
    _, _, body = _request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return json.loads(body.decode("utf-8", errors="replace"))


def _json_post(url: str, obj: dict) -> dict:
    payload = json.dumps(obj).encode("utf-8")
    _, _, body = _request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(body.decode("utf-8", errors="replace"))


def _json_get(url: str, params: dict) -> dict:
    full = url + "?" + urlencode(params)
    _, _, body = _request(full, method="GET")
    return json.loads(body.decode("utf-8", errors="replace"))


def _retry(fn, retries: int = 3):
    last = None
    delay = 2.0
    for attempt in range(retries):
        try:
            return fn()
        except BcutError as exc:
            last = exc
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise last or BcutError("retry failed")


def _check_api(resp: dict, step: str) -> dict:
    if not isinstance(resp, dict):
        raise BcutError(f"{step}: 非 JSON 对象")
    code = resp.get("code")
    if code not in (0, None):
        raise BcutError(f"{step}: code={code} {resp.get('message') or resp.get('msg')}")
    data = resp.get("data")
    if data is None:
        raise BcutError(f"{step}: 无 data")
    return data


class BcutClient:
    def upload(self, name: str, blob: bytes, fmt: str) -> str:
        def create():
            return _json_post_form(
                API_REQ_UPLOAD,
                {
                    "type": "2",
                    "name": name,
                    "size": str(len(blob)),
                    "resource_file_type": fmt,
                    "model_id": str(MODEL_ID),
                },
            )

        data = _check_api(_retry(create), "resource.create")
        upload_urls = data.get("upload_urls") or []
        if not upload_urls:
            raise BcutError("resource.create 没有 upload_urls")
        per_size = int(data.get("per_size") or len(blob) or 1)
        etags = []
        for i, url in enumerate(upload_urls):
            start = i * per_size
            chunk = blob[start:start + per_size]
            def put(u=url, c=chunk):
                status, headers, _ = _request(u, method="PUT", data=c, timeout=120)
                if status >= 400:
                    raise BcutError(f"分片上传 HTTP {status}")
                return headers.get("Etag") or headers.get("ETag") or headers.get("etag") or str(uuid.uuid4())

            etags.append(_retry(lambda: put()))
        complete = _retry(
            lambda: _json_post_form(
                API_COMMIT_UPLOAD,
                {
                    "in_boss_key": data["in_boss_key"],
                    "resource_id": data["resource_id"],
                    "etags": ",".join(etags),
                    "upload_id": data["upload_id"],
                    "model_id": str(MODEL_ID),
                },
            )
        )
        cdata = _check_api(complete, "resource.complete")
        return cdata["download_url"]

    def create_task(self, download_url: str) -> str:
        resp = _retry(lambda: _json_post(API_CREATE_TASK, {"resource": download_url, "model_id": str(MODEL_ID)}))
        data = _check_api(resp, "task.create")
        return data["task_id"]

    def poll(self, task_id: str, timeout: int = 900, interval: float = 2.0) -> dict:
        deadline = time.time() + timeout
        last_state = None
        while time.time() < deadline:
            resp = _json_get(API_QUERY_RESULT, {"model_id": str(MODEL_ID), "task_id": task_id})
            data = _check_api(resp, "task.result")
            state = data.get("state")
            last_state = state
            # 0 STOP, 1 RUNNING, 3 ERROR, 4 COMPLETE (SocialSisterYi/bcut-asr)
            if state == 4:
                return data
            if state == 3:
                raise BcutError(f"识别失败: {data.get('remark')}")
            time.sleep(interval)
            if interval < 8:
                interval = min(8.0, interval + 1.0)
        raise BcutError(f"轮询超时 last_state={last_state}", code="E_TIMEOUT")


def utterances_to_segments(result_json: str | dict) -> list[dict]:
    if isinstance(result_json, str):
        try:
            obj = json.loads(result_json)
        except json.JSONDecodeError as exc:
            raise BcutError(f"结果 JSON 无法解析: {exc}") from exc
    else:
        obj = result_json
    utterances = obj.get("utterances") or []
    segs = []
    for u in utterances:
        text = (u.get("transcript") or u.get("text") or "").strip()
        if not text:
            continue
        start_ms = int(u.get("start_time") or 0)
        end_ms = int(u.get("end_time") or start_ms)
        segs.append({"start": start_ms / 1000.0, "end": end_ms / 1000.0, "text": text})
    return segs


def transcribe_file(audio_path: str | Path, workdir: Optional[Path] = None, timeout: int = 900) -> list[dict]:
    path = Path(audio_path)
    if not path.exists():
        raise BcutError(f"音频不存在: {path}", code="E_NO_MEDIA")
    wd = workdir or workdir_for(path.stem)
    converted = convert_for_bcut(path, wd)
    fmt = converted.suffix.lstrip(".").lower()
    client = BcutClient()
    blob = converted.read_bytes()
    download_url = client.upload(converted.name, blob, fmt)
    task_id = client.create_task(download_url)
    data = client.poll(task_id, timeout=timeout)
    raw_path = wd / f"{path.stem}.bcut.json"
    dump_json(raw_path, data)
    result = data.get("result")
    segs = utterances_to_segments(result or {})
    if not segs:
        raise BcutError("返回空文本", code="E_NO_SPEECH")
    srt_path = wd / f"{path.stem}.bcut.srt"
    srt_path.write_text(_to_srt(segs), encoding="utf-8")
    return segs


def _to_srt(segs: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segs, 1):
        def fmt(t: float) -> str:
            ms = int(round(t * 1000))
            h, rem = divmod(ms, 3600000)
            m, rem = divmod(rem, 60000)
            s, milli = divmod(rem, 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"
        lines.append(f"{i}\n{fmt(seg['start'])} --> {fmt(seg['end'])}\n{seg['text']}\n")
    return "\n".join(lines)


def transcribe(audio_path: str, workdir: Optional[str] = None, timeout: int = 900) -> list[dict]:
    path = Path(audio_path)
    wd = Path(workdir) if workdir else workdir_for(path.stem)
    duration = probe_duration(path)
    if need_slice(path, duration):
        slices_dir = wd / "slices"
        chunks = slice_audio(path, slices_dir, duration=duration)
        pieces = []
        for chunk_path, offset in chunks:
            segs = transcribe_file(chunk_path, wd, timeout=timeout)
            pieces.append((offset, segs))
        return merge_sliced_segments(pieces, overlap_sec=2.0)
    return transcribe_file(path, wd, timeout=timeout)


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Bcut cloud ASR")
    parser.add_argument("audio")
    parser.add_argument("--workdir")
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    path = Path(args.audio)
    try:
        segs = transcribe(str(path), workdir=args.workdir, timeout=args.timeout)
    except BcutError as exc:
        die(exc.code, exc.message, "可改用本地 Whisper: python scripts/asr_whisper.py AUDIO --out segments.json")
    payload = {
        "segments": segs,
        "transcript_source": "bcut-asr",
        "count": len(segs),
        "audio_path": str(path),
        "note": "Bcut ASR（云端，音频已上传）",
        "duration_hms": format_hms(probe_duration(path)),
        "size_bytes": file_size(path) if path.exists() else None,
    }
    dump_json(Path(args.out), payload)
    ok(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
