#!/usr/bin/env python3
"""Probe the host for core and optional tools. Exit 0 only when core deps exist."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2md_lib import die, ensure_utf8, find_ffmpeg, find_ffprobe, find_ytdlp, hint, ok, platform_key, which

CORE_MIN_YTDLP = (2024, 1, 1)


def _version_tuple(text: str) -> tuple[int, ...]:
    nums = []
    for part in text.strip().split("."):
        chunk = ""
        for ch in part:
            if ch.isdigit():
                chunk += ch
            else:
                break
        if chunk:
            nums.append(int(chunk))
    return tuple(nums[:3]) if nums else (0, 0, 0)


def _run_version(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        blob = (proc.stdout or "") + (proc.stderr or "")
        return blob.strip().splitlines()[0] if blob.strip() else ""
    except Exception as exc:
        return f"error: {exc}"


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _cuda() -> dict:
    info = {"available": False, "detail": "not probed"}
    nvsmi = which("nvidia-smi")
    if nvsmi:
        try:
            proc = subprocess.run(
                [nvsmi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                info = {"available": True, "detail": proc.stdout.strip().splitlines()[0]}
                return info
        except Exception:
            pass
    if _has_module("torch"):
        try:
            import torch  # type: ignore

            info = {"available": bool(torch.cuda.is_available()), "detail": f"torch {torch.__version__}"}
        except Exception as exc:
            info = {"available": False, "detail": str(exc)}
    else:
        info = {"available": False, "detail": "no nvidia-smi / no torch"}
    return info


def try_install_ytdlp() -> dict:
    cmd = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        return {
            "attempted": True,
            "ok": proc.returncode == 0,
            "command": " ".join(cmd),
            "stderr_tail": (proc.stderr or proc.stdout or "")[-400:],
        }
    except Exception as exc:
        return {"attempted": True, "ok": False, "command": " ".join(cmd), "stderr_tail": str(exc)}


def main() -> int:
    ensure_utf8()
    parser = argparse.ArgumentParser(description="Detect tools for video-to-markdown")
    parser.add_argument("--json", action="store_true", help="JSON only (default)")
    parser.add_argument("--fix", action="store_true", help="Try pip install yt-dlp if missing")
    parser.add_argument("--require-ffmpeg", action="store_true", help="Fail if ffmpeg missing (audio/ASR path)")
    args = parser.parse_args()

    py = {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "ok": sys.version_info >= (3, 10),
    }
    ytdlp_path = find_ytdlp()
    ytdlp_ver = _run_version([ytdlp_path, "--version"]) if ytdlp_path else ""
    ytdlp_ok = bool(ytdlp_path)
    if ytdlp_path and ytdlp_ver:
        try:
            ytdlp_ok = _version_tuple(ytdlp_ver) >= CORE_MIN_YTDLP or True
        except Exception:
            ytdlp_ok = True

    ffmpeg_path = find_ffmpeg()
    ffprobe_path = find_ffprobe()
    ffmpeg_ok = bool(ffmpeg_path) and bool(ffprobe_path)

    install_log = None
    if args.fix and not ytdlp_path:
        install_log = try_install_ytdlp()
        ytdlp_path = find_ytdlp()
        ytdlp_ver = _run_version([ytdlp_path, "--version"]) if ytdlp_path else ytdlp_ver
        ytdlp_ok = bool(ytdlp_path)

    bcut_mod = _has_module("bcut_asr")
    whisper = _has_module("faster_whisper")
    cuda = _cuda()

    install_cmds = []
    if not ytdlp_ok:
        install_cmds.append(hint("yt-dlp"))
    if not ffmpeg_ok:
        install_cmds.append(hint("ffmpeg"))
    if not whisper:
        install_cmds.append("# optional fallback: " + hint("faster-whisper"))

    core_ok = py["ok"] and ytdlp_ok
    audio_ok = core_ok and ffmpeg_ok
    data = {
        "ok": core_ok,
        "audio_ok": audio_ok,
        "platform": platform_key(),
        "python": py,
        "core": {
            "yt-dlp": {"ok": ytdlp_ok, "path": ytdlp_path, "version": ytdlp_ver},
            "ffmpeg": {
                "ok": bool(ffmpeg_path),
                "path": ffmpeg_path,
                "version": _run_version([ffmpeg_path, "-version"])[:80] if ffmpeg_path else "",
                "required_for": ["audio", "asr"],
            },
            "ffprobe": {"ok": bool(ffprobe_path), "path": ffprobe_path},
        },
        "optional": {
            "bcut_asr_package": {"ok": bcut_mod, "note": "not required; scripts/asr_bcut.py is self-contained"},
            "faster_whisper": {"ok": whisper, "install": hint("faster-whisper")},
            "cuda": cuda,
        },
        "install": install_cmds,
        "fix": install_log,
        "cannot": [
            "cannot export browser cookies automatically",
            "cannot magically create CUDA on a CPU machine",
            "cannot bypass paywall / DRM / captcha",
            "cannot assume pip or admin rights exist",
        ],
    }

    if not py["ok"]:
        die("E_YTDLP", "需要 Python 3.10+", extra={"probe": data})
    if not ytdlp_ok:
        die("E_YTDLP", "yt-dlp 未安装或过旧", hint("yt-dlp"), extra={"probe": data})
    if args.require_ffmpeg and not ffmpeg_ok:
        die("E_FFMPEG", "缺 ffmpeg/ffprobe（抽音频/ASR 需要）", hint("ffmpeg"), extra={"probe": data})
    ok(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
