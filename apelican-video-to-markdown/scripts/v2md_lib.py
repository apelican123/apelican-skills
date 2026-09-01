#!/usr/bin/env python3
"""Shared helpers for apelican-video-to-markdown scripts."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ERROR_CODES = (
    "E_BAD_URL",
    "E_UNSUPPORTED",
    "E_PRIVACY",
    "E_MEMBER",
    "E_AGE",
    "E_GEO",
    "E_COOKIE",
    "E_NO_MEDIA",
    "E_NO_SPEECH",
    "E_YTDLP",
    "E_FFMPEG",
    "E_BCUT",
    "E_WHISPER",
    "E_TIMEOUT",
)

LOCAL_MEDIA_EXT = {".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".opus"}
BCUT_AUDIO_EXT = {".flac", ".aac", ".m4a", ".mp3", ".wav"}
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
AV_RE = re.compile(r"(?:av|AV)(\d+)")
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DANMAKU_RE = re.compile(r"danmaku|弹幕", re.I)

INSTALL_HINTS = {
    "yt-dlp": {
        "windows": "pip install -U yt-dlp",
        "darwin": "pip install -U yt-dlp  # or: brew install yt-dlp",
        "linux": "pip install -U yt-dlp",
    },
    "ffmpeg": {
        "windows": "winget install Gyan.FFmpeg",
        "darwin": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg",
    },
    "faster-whisper": {
        "windows": "pip install -U faster-whisper",
        "darwin": "pip install -U faster-whisper",
        "linux": "pip install -U faster-whisper",
    },
}


def ensure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8")
            except Exception:
                pass


def platform_key() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def hint(tool: str) -> str:
    return INSTALL_HINTS.get(tool, {}).get(platform_key(), f"install {tool}")


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def die(code: str, message: str, hint_text: Optional[str] = None, extra: Optional[dict] = None) -> None:
    payload = {
        "ok": False,
        "error": {"code": code, "message": message, "hint": hint_text},
    }
    if extra:
        payload["error"]["extra"] = extra
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    line = f"{code}: {message}"
    if hint_text:
        line += f" | {hint_text}"
    print(line, file=sys.stderr, flush=True)
    raise SystemExit(1)


def ok(data: Any) -> None:
    print(json.dumps({"ok": True, "error": None, "data": data}, ensure_ascii=False, indent=2), flush=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def format_hms(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"
    total = max(0, int(round(float(seconds))))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ms_to_seconds(ms: Any) -> float:
    return float(ms) / 1000.0


def seconds_to_ms(sec: Any) -> int:
    return int(round(float(sec) * 1000))


def safe_filename(title: str, limit: int = 48) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t！!？?《》【】（）()、，。,.]', " ", title or "untitled")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "untitled"
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip(" .")
    return cleaned


# Windows/POSIX 文件名都不能含 ASCII `/`。规范写法是 2026/09/01-标题，落盘用全角斜杠。
DATE_SLASH = "\uFF0F"


def dated_markdown_name(title: str, when: Optional[datetime] = None) -> str:
    d = (when or datetime.now().astimezone()).date()
    date_part = f"{d.year:04d}{DATE_SLASH}{d.month:02d}{DATE_SLASH}{d.day:02d}"
    return f"{date_part}-{safe_filename(title, 60)}.md"


def run_cmd(
    args: list[str],
    *,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
        check=check,
    )


def _win_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def _extra_bin_dirs() -> list[Path]:
    home = _win_home()
    local = Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local"))
    dirs = [
        home / ".local" / "bin",
        local / "Microsoft" / "WinGet" / "Links",
        Path(r"C:/ffmpeg/bin"),
        Path(r"C:/Program Files/ffmpeg/bin"),
        Path(r"C:/Program Files/Gyan/FFmpeg/bin"),
    ]
    winget_pkgs = local / "Microsoft" / "WinGet" / "Packages"
    if winget_pkgs.exists():
        dirs.extend(sorted(winget_pkgs.glob("Gyan.FFmpeg*/ffmpeg-*/bin"), reverse=True)[:6])
        dirs.extend(sorted(winget_pkgs.glob("Gyan.FFmpeg*/bin"), reverse=True)[:4])
    env_ffmpeg = os.environ.get("FFMPEG") or os.environ.get("FFMPEG_BINARY")
    if env_ffmpeg:
        p = Path(env_ffmpeg)
        dirs.append(p.parent if p.is_file() else p)
    return dirs


def _which_or_extra(names: tuple[str, ...]) -> Optional[str]:
    for name in names:
        path = which(name)
        if path:
            return path
    for folder in _extra_bin_dirs():
        for name in names:
            cand = folder / name
            if cand.exists():
                return str(cand)
    return None


def find_ytdlp() -> Optional[str]:
    return _which_or_extra(("yt-dlp", "yt-dlp.exe"))


def find_ffmpeg() -> Optional[str]:
    return _which_or_extra(("ffmpeg", "ffmpeg.exe"))


def find_ffprobe() -> Optional[str]:
    return _which_or_extra(("ffprobe", "ffprobe.exe"))


def ffmpeg_location() -> Optional[str]:
    exe = find_ffmpeg()
    return str(Path(exe).parent) if exe else None


def ytdlp_cmd(extra: Iterable[str] | None = None) -> list[str]:
    bin_path = find_ytdlp()
    if not bin_path:
        die("E_YTDLP", "yt-dlp 未安装", hint("yt-dlp"))
    cmd = [bin_path]
    if extra:
        cmd.extend(extra)
    return cmd


def cookie_args(browser: Optional[str] = None, cookies_file: Optional[str] = None) -> list[str]:
    args: list[str] = []
    if cookies_file:
        args.extend(["--cookies", cookies_file])
    elif browser:
        args.extend(["--cookies-from-browser", browser])
    return args


class NormalizedInput:
    def __init__(
        self,
        kind: str,
        raw: str,
        url: Optional[str] = None,
        path: Optional[Path] = None,
        site: str = "other",
        video_id: str = "",
        page: Optional[int] = None,
        is_playlist: bool = False,
    ) -> None:
        self.kind = kind
        self.raw = raw
        self.url = url
        self.path = path
        self.site = site
        self.video_id = video_id
        self.page = page
        self.is_playlist = is_playlist

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "raw": self.raw,
            "url": self.url,
            "path": str(self.path) if self.path else None,
            "site": self.site,
            "video_id": self.video_id,
            "page": self.page,
            "is_playlist": self.is_playlist,
        }

    def ytdlp_target(self) -> str:
        if self.kind == "local":
            return str(self.path)
        return self.url or self.raw


def _expand_b23(url: str) -> str:
    try:
        req = Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as resp:
            return resp.geturl() or url
    except Exception:
        return url


def normalize_input(raw: str) -> NormalizedInput:
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        die("E_BAD_URL", "空输入，给一个视频 URL、BV 号或本地文件")

    local = Path(text).expanduser()
    if local.exists() and local.is_file():
        suffix = local.suffix.lower()
        if suffix not in LOCAL_MEDIA_EXT:
            die("E_BAD_URL", f"本地文件不是支持的音视频格式: {suffix}")
        return NormalizedInput(
            kind="local",
            raw=text,
            path=local.resolve(),
            site="local",
            video_id=local.stem,
        )

    if text.startswith("http://") or text.startswith("https://"):
        url = text
        if "b23.tv" in url or "b23.wtf" in url:
            url = _expand_b23(url)
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        query = parse_qs(parsed.query)
        page = None
        if "p" in query:
            try:
                page = int(query["p"][0])
            except Exception:
                page = None
        if "bilibili.com" in host or "b23.tv" in host:
            bv = BV_RE.search(url)
            av = AV_RE.search(url)
            vid = bv.group(1) if bv else (f"av{av.group(1)}" if av else "")
            is_list = "/medialist" in parsed.path or "playlist" in parsed.path or bool(query.get("list"))
            return NormalizedInput("url", text, url=url, site="bilibili", video_id=vid, page=page, is_playlist=is_list)
        if "youtube.com" in host or "youtu.be" in host or "youtube-nocookie.com" in host:
            vid = ""
            if "youtu.be" in host:
                vid = parsed.path.strip("/").split("/")[0]
            else:
                if query.get("v"):
                    vid = query["v"][0]
                else:
                    m = re.search(r"/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})", parsed.path)
                    if m:
                        vid = m.group(1)
            is_list = "list" in query or parsed.path.startswith("/playlist")
            return NormalizedInput("url", text, url=url, site="youtube", video_id=vid, page=page, is_playlist=is_list)
        return NormalizedInput("url", text, url=url, site="other", is_playlist="list=" in url or "/playlist" in url)

    bv = BV_RE.fullmatch(text) or BV_RE.search(text)
    if bv and len(text) <= 20:
        vid = bv.group(1)
        return NormalizedInput(
            "url",
            text,
            url=f"https://www.bilibili.com/video/{vid}",
            site="bilibili",
            video_id=vid,
        )
    av = AV_RE.fullmatch(text)
    if av:
        vid = f"av{av.group(1)}"
        return NormalizedInput(
            "url",
            text,
            url=f"https://www.bilibili.com/video/{vid}",
            site="bilibili",
            video_id=vid,
        )
    if YT_ID_RE.match(text):
        return NormalizedInput(
            "url",
            text,
            url=f"https://www.youtube.com/watch?v={text}",
            site="youtube",
            video_id=text,
        )
    die("E_BAD_URL", f"解析不出视频: {text}")
    raise AssertionError


def map_ytdlp_error(text: str) -> tuple[str, str]:
    blob = text or ""
    low = blob.lower()
    if "unsupported url" in low or "no suitable extractor" in low:
        return "E_UNSUPPORTED", "yt-dlp 没有这个站点的提取器"
    if "this live event" in low or "livestream" in low and "not currently available" in low:
        return "E_UNSUPPORTED", "正在进行的直播，未结束流不转写"
    if "private video" in low or "this video is private" in low or "登录" in blob and "私有" in blob:
        return "E_PRIVACY", "视频私密或未发布，需要登录"
    if any(k in low for k in ("members only", "members-only", "join this channel")) or "大会员" in blob or "充电" in blob or "付费" in blob:
        return "E_MEMBER", "需要会员/充电/付费身份 Cookie"
    if "confirm your age" in low or "age-restricted" in low or "年龄" in blob:
        return "E_AGE", "年龄限制，需要登录 Cookie"
    if any(k in low for k in ("not available in your country", "geo", "region")) or "地区" in blob:
        return "E_GEO", "地区限制"
    if "412" in blob or "precondition" in low or "风控" in blob:
        return "E_COOKIE", "412/风控，需要浏览器 Cookie"
    if "could not copy" in low and "cookie" in low:
        return "E_COOKIE", "浏览器 Cookie 数据库被占用（先关浏览器，或换 edge/firefox）"
    if "failed to decrypt with dpapi" in low or "oscrypt" in low:
        return "E_COOKIE", "Cookie 解密失败（Chromium DPAPI）。换 firefox 或导出 cookies.txt"
    if "sign in" in low or "login required" in low or "http error 401" in low or "http error 403" in low:
        return "E_COOKIE", "需要登录 Cookie"
    if "drm" in low:
        return "E_NO_MEDIA", "DRM 保护，无法取流"
    if any(k in low for k in ("no video formats", "requested format is not available", "has been removed", "video unavailable")):
        return "E_NO_MEDIA", "无可用音视频流，可能下架"
    if "http error 429" in low:
        return "E_TIMEOUT", "yt-dlp 被限流"
    return "E_NO_MEDIA", blob.strip().splitlines()[-1] if blob.strip() else "yt-dlp 失败"


COOKIE_RETRYABLE = {"E_COOKIE", "E_PRIVACY", "E_AGE", "E_MEMBER"}
BROWSER_CHAIN = ("chrome", "edge", "firefox")


def run_ytdlp(
    prefix: list[str],
    target: str,
    *,
    timeout: int,
    browser: Optional[str] = None,
    cookies: Optional[str] = None,
    auto_cookies: bool = True,
):
    """Run yt-dlp. If no cookie args given, try none → chrome → edge → firefox on login/412 errors."""
    if cookies:
        chain = [("cookies.txt", cookie_args(None, cookies))]
    elif browser:
        chain = [(browser, cookie_args(browser, None))]
    elif auto_cookies:
        chain = [("none", [])] + [(b, cookie_args(b, None)) for b in BROWSER_CHAIN]
    else:
        chain = [("none", [])]

    last_code, last_msg, last_blob, last_src = "E_COOKIE", "需要 Cookie", "", "none"
    for label, cargs in chain:
        cmd = list(prefix) + cargs + [target]
        try:
            proc = run_cmd(cmd, timeout=timeout)
        except Exception as exc:
            last_code, last_msg, last_blob, last_src = "E_TIMEOUT", f"yt-dlp 超时: {exc}", str(exc), label
            continue
        if proc.returncode == 0:
            return proc, label
        blob = (proc.stderr or "") + "\n" + (proc.stdout or "")
        code, msg = map_ytdlp_error(blob)
        last_code, last_msg, last_blob, last_src = code, msg, blob, label
        if code not in COOKIE_RETRYABLE:
            die(code, msg, extra={"stderr_tail": blob[-800:], "cookie_source": label})
    hint = "已按 none→chrome→edge→firefox 试过。可关掉浏览器再试，或 --cookies cookies.txt"
    if cookies or browser:
        hint = "指定的 Cookie 源失败。换 firefox，或导出 cookies.txt"
    die(last_code, last_msg, hint, extra={"stderr_tail": last_blob[-800:], "cookie_source": last_src})
    raise AssertionError


def probe_duration(path: Path) -> Optional[float]:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return None
    proc = run_cmd(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        timeout=60,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip().splitlines()[0])
    except Exception:
        return None


def file_size(path: Path) -> int:
    return path.stat().st_size


def need_slice(path: Path, duration: Optional[float] = None) -> bool:
    dur = duration if duration is not None else probe_duration(path)
    if dur is not None and dur > 20 * 60:
        return True
    try:
        if file_size(path) > 80 * 1024 * 1024:
            return True
    except OSError:
        pass
    return False


def slice_audio(
    path: Path,
    workdir: Path,
    *,
    slice_sec: int = 12 * 60,
    overlap_sec: int = 2,
    duration: Optional[float] = None,
) -> list[tuple[Path, float]]:
    """Return [(chunk_path, start_offset_sec), ...]."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        die("E_FFMPEG", "切片需要 ffmpeg", hint("ffmpeg"))
    dur = duration if duration is not None else probe_duration(path)
    if dur is None:
        die("E_FFMPEG", f"无法读取音频时长: {path}")
    workdir.mkdir(parents=True, exist_ok=True)
    chunks: list[tuple[Path, float]] = []
    start = 0.0
    idx = 0
    while start < dur - 0.5:
        length = min(slice_sec, dur - start)
        out = workdir / f"slice_{idx:03d}{path.suffix or '.m4a'}"
        proc = run_cmd(
            [
                ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                "-i", str(path), "-vn", "-c", "copy", str(out),
            ],
            timeout=300,
        )
        if proc.returncode != 0 or not out.exists() or out.stat().st_size < 64:
            proc = run_cmd(
                [
                    ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                    "-i", str(path), "-vn", "-acodec", "libmp3lame", "-q:a", "2",
                    str(out.with_suffix(".mp3")),
                ],
                timeout=300,
            )
            out = out.with_suffix(".mp3")
            if proc.returncode != 0 or not out.exists():
                die("E_FFMPEG", f"切片失败: {proc.stderr[-400:]}")
        chunks.append((out, start))
        idx += 1
        if start + length >= dur:
            break
        start = start + slice_sec - overlap_sec
    return chunks


def convert_for_bcut(path: Path, workdir: Path) -> Path:
    if path.suffix.lower() in BCUT_AUDIO_EXT:
        return path
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        die("E_FFMPEG", "当前音频容器 Bcut 不认，需要 ffmpeg 转码", hint("ffmpeg"))
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / (path.stem + ".mp3")
    proc = run_cmd(
        [ffmpeg, "-y", "-i", str(path), "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(out)],
        timeout=600,
    )
    if proc.returncode != 0 or not out.exists():
        die("E_FFMPEG", f"转码 mp3 失败: {proc.stderr[-400:]}", hint("ffmpeg"))
    return out


def merge_sliced_segments(
    pieces: list[tuple[float, list[dict]]],
    overlap_sec: float = 2.0,
) -> list[dict]:
    merged: list[dict] = []
    last_end = -1.0
    for offset, segs in pieces:
        for seg in segs:
            start = float(seg["start"]) + offset
            end = float(seg["end"]) + offset
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            if merged and start < last_end - 0.3:
                continue
            merged.append({"start": start, "end": end, "text": text})
            last_end = end
    return merged


def is_danmaku_lang(key: str) -> bool:
    return bool(DANMAKU_RE.search(key or ""))


def iter_caption_tracks(info: dict) -> list[dict]:
    tracks = []
    for bucket, automatic in (("subtitles", False), ("automatic_captions", True)):
        mapping = info.get(bucket) or {}
        if not isinstance(mapping, dict):
            continue
        for lang, items in mapping.items():
            if is_danmaku_lang(str(lang)):
                continue
            if not items:
                continue
            ext = ""
            url = ""
            if isinstance(items, list) and items:
                preferred = None
                for it in items:
                    if isinstance(it, dict) and it.get("ext") in {"srt", "vtt", "json3", "json", "ass"}:
                        preferred = it
                        break
                preferred = preferred or (items[0] if isinstance(items[0], dict) else None)
                if preferred:
                    ext = preferred.get("ext") or ""
                    url = preferred.get("url") or ""
            tracks.append(
                {
                    "lang": str(lang),
                    "automatic": automatic,
                    "ext": ext,
                    "url": url,
                    "bucket": bucket,
                }
            )
    return tracks


def pick_subtitle_track(info: dict, site: str, prefer_lang: Optional[str] = None) -> Optional[dict]:
    tracks = iter_caption_tracks(info)
    if not tracks:
        return None
    if prefer_lang:
        for t in tracks:
            if t["lang"].lower().startswith(prefer_lang.lower()) and not t["automatic"]:
                return t
        for t in tracks:
            if t["lang"].lower().startswith(prefer_lang.lower()):
                return t

    def score(t: dict) -> tuple:
        lang = t["lang"].lower()
        auto = 1 if t["automatic"] else 0
        if site == "bilibili":
            if lang in {"ai-zh", "ai_zh"}:
                return (0, auto, 0)
            if lang in {"zh-hans", "zh-cn", "zh", "zh-hant", "zh-tw"}:
                return (1, auto, 0)
            if lang.startswith("zh"):
                return (2, auto, 0)
            return (5, auto, 0)
        if site == "youtube":
            order = 0 if not auto else 3
            if prefer_lang and lang.startswith(prefer_lang.lower()):
                return (order, 0, 0)
            if lang.startswith("zh"):
                return (order, 1, 0)
            if lang.startswith("en"):
                return (order, 2, 0)
            return (order + 1, 3, 0)
        return (0 if not auto else 2, 0, 0)

    tracks.sort(key=score)
    return tracks[0]


def transcript_source_of(track: Optional[dict], asr: Optional[str] = None) -> str:
    if asr == "bcut":
        return "bcut-asr"
    if asr == "whisper":
        return "faster-whisper"
    if not track:
        return "unknown"
    lang = (track.get("lang") or "").lower()
    if lang in {"ai-zh", "ai_zh"}:
        return "official-ai-sub"
    if track.get("automatic"):
        return "yt-auto-sub"
    return "official-cc"


def parse_timestamp_to_seconds(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def parse_srt(text: str) -> list[dict]:
    segments = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    time_re = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
    )
    for block in blocks:
        lines = [ln.strip("\ufeff") for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        time_line = None
        text_start = 0
        for i, ln in enumerate(lines):
            if "-->" in ln:
                time_line = ln
                text_start = i + 1
                break
        if not time_line:
            continue
        m = time_re.search(time_line)
        if not m:
            continue
        body = " ".join(lines[text_start:]).strip()
        body = re.sub(r"<[^>]+>", "", body)
        if not body:
            continue
        segments.append(
            {
                "start": parse_timestamp_to_seconds(m.group(1)),
                "end": parse_timestamp_to_seconds(m.group(2)),
                "text": body,
            }
        )
    return segments


def parse_vtt(text: str) -> list[dict]:
    cleaned = re.sub(r"^WEBVTT.*\n", "", text.replace("\r\n", "\n"), flags=re.I)
    return parse_srt(cleaned)


def parse_bilibili_json_sub(data: Any) -> list[dict]:
    segs = []
    body = data
    if isinstance(data, dict):
        body = data.get("body") or data.get("utterances") or data.get("data") or []
    if not isinstance(body, list):
        return segs
    for item in body:
        if not isinstance(item, dict):
            continue
        text = (item.get("content") or item.get("transcript") or item.get("text") or "").strip()
        if not text:
            continue
        if "from" in item:
            start = float(item.get("from") or 0)
            end = float(item.get("to") or start)
        elif "start_time" in item:
            start = ms_to_seconds(item.get("start_time") or 0)
            end = ms_to_seconds(item.get("end_time") or item.get("start_time") or 0)
        else:
            start = float(item.get("start") or 0)
            end = float(item.get("end") or start)
        segs.append({"start": start, "end": end, "text": text})
    return segs


def parse_subtitle_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            return parse_bilibili_json_sub(json.loads(raw))
        except json.JSONDecodeError:
            return []
    if suffix == ".vtt":
        return parse_vtt(raw)
    return parse_srt(raw)


def workdir_for(video_id: str, root: Optional[Path] = None) -> Path:
    base = root or (Path.cwd() / "transcripts" / ".work")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", video_id or "video")[:40] or "video"
    path = base / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def sidecar_subs(media: Path) -> list[Path]:
    found = []
    for ext in (".srt", ".vtt", ".ass", ".json"):
        p = media.with_suffix(ext)
        if p.exists():
            found.append(p)
    return found
