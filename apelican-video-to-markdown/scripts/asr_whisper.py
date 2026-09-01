#!/usr/bin/env python3
"""Local faster-whisper fallback. Do not install large-v3 by default."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import (
    die,
    dump_json,
    ensure_utf8,
    find_ffmpeg,
    format_hms,
    hint,
    merge_sliced_segments,
    need_slice,
    ok,
    probe_duration,
    slice_audio,
    workdir_for,
)


def _device_and_compute() -> tuple[str, str, str]:
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda", "float16", "GPU"
    except Exception:
        pass
    return "cpu", "int8", "CPU（会很慢）"


def transcribe_once(audio_path: Path, model_size: str, language: str | None) -> list[dict]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        die("E_WHISPER", "未安装 faster-whisper", hint("faster-whisper"))

    device, compute, _ = _device_and_compute()
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute)
    except Exception as exc:
        die("E_WHISPER", f"加载模型失败 ({model_size}): {exc}", hint("faster-whisper"))
    try:
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
            beam_size=5,
        )
    except Exception as exc:
        die("E_WHISPER", f"识别失败: {exc}")
    segs = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        segs.append({"start": float(seg.start), "end": float(seg.end), "text": text})
    return segs


def transcribe(audio_path: str, model_size: str = "small", language: str | None = None, workdir: str | None = None) -> list[dict]:
    path = Path(audio_path)
    if not path.exists():
        die("E_NO_MEDIA", f"音频不存在: {path}")
    if not find_ffmpeg():
        die("E_FFMPEG", "Whisper 切片/转码需要 ffmpeg", hint("ffmpeg"))
    wd = Path(workdir) if workdir else workdir_for(path.stem)
    duration = probe_duration(path)
    if need_slice(path, duration):
        pieces = []
        for chunk, offset in slice_audio(path, wd / "whisper_slices", duration=duration):
            pieces.append((offset, transcribe_once(chunk, model_size, language)))
        segs = merge_sliced_segments(pieces)
    else:
        segs = transcribe_once(path, model_size, language)
    if not segs:
        die("E_NO_SPEECH", "Whisper 没有识别到对白")
    return segs


def pick_default_model(lang: str | None, duration: float | None) -> str:
    if lang and lang.lower().startswith("en") and duration and duration < 10 * 60:
        return "base"
    return "small"


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Local faster-whisper ASR")
    parser.add_argument("audio")
    parser.add_argument("--model", default=None, help="tiny/base/small/medium/large-v3. Default small (base for short English)")
    parser.add_argument("--language", default=None)
    parser.add_argument("--workdir")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    path = Path(args.audio)
    duration = probe_duration(path)
    model = args.model or pick_default_model(args.language, duration)
    if model in {"large", "large-v2", "large-v3"}:
        # allowed only when user named it; still warn in payload
        pass
    device, _, device_note = _device_and_compute()
    segs = transcribe(str(path), model_size=model, language=args.language, workdir=args.workdir)
    payload = {
        "segments": segs,
        "transcript_source": "faster-whisper",
        "count": len(segs),
        "model": model,
        "device": device,
        "device_note": device_note,
        "audio_path": str(path),
        "duration_hms": format_hms(duration),
    }
    dump_json(Path(args.out), payload)
    ok(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
