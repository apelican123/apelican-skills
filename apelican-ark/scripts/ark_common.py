#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ark_common.py — 共享规则与工具：ark 备份/恢复技能（v1.0）

职责：
- 定位 Codex / WorkBuddy 主目录（支持 CODEX_HOME 环境变量覆盖）
- 目录与文件分类规则（技能识别、运行时排除、敏感排除）
- 密钥扫描与脱敏（JSON 结构脱敏 + 行级脱敏）
- 哈希、软链接、frontmatter 解析等工具函数

设计原则：
- 零第三方依赖，仅 Python 标准库（3.10+）
- 分类三轨：白名单（根级配置）+ 语义识别（技能目录）+ 排除清单（运行时/敏感）
- 一切判定可审计：每个文件都带 reason/type 写入 manifest
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2.0"
TOOL_NAME = "ark"
TOOL_VERSION = "3.0.0"

# ---------------------------------------------------------------------------
# 主目录定位
# ---------------------------------------------------------------------------


def home_dir() -> Path:
    return Path(os.path.expanduser("~"))


def codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else home_dir() / ".codex"


def workbuddy_home() -> Path:
    env = os.environ.get("WORKBUDDY_HOME")
    return Path(env) if env else home_dir() / ".workbuddy"


# ---------------------------------------------------------------------------
# 排除清单：按"任何级别 / 会话类 / 密钥类"三档拆分
# - CACHE_DIRS：任何备份级别都排除（缓存、临时、日志、可重建）
# - SESSION_DIRS：basic/advanced 排除，--profile full 时放行（对话历史）
# - ACCOUNT_STATE_*：账号登录、Cookie、设备绑定授权；任何级别都排除
# - SECRET_DIRS / SECRET_FILES：用户自管的敏感配置；仅单独确认后进入 AES 包
# ---------------------------------------------------------------------------

CACHE_DIRS = {
    ".git", ".tmp", ".sandbox", ".sandbox-bin", ".sandbox-secrets",
    "logs", "cache", "blobs", "traces", "tasks", "plans", "teams",
    "app", "vendor", "binaries", "local_storage", "pending-telemetry",
    "audit-log", "artifact-index", "clipboard-images", "shell-snapshots",
    "file-history", "plugin-marketplace-state", "plugin-marketplace-state-new",
    "claw-state", ".workbuddy-sqlite-migrations", "backups",
    "automation-backups", "extensions", "mcp-oauth-locks",
    "connectors-marketplace",
}

# 会话类：full 级别尽力备份本地可见文件；不承诺客户端完整显示
SESSION_DIRS = {
    "sessions", "archived_sessions", "attachments", "generated_images",
    "dictation-history", "computer-use", "browser", "ambient-suggestions",
}

# 账号登录与设备绑定状态：即使文件可复制，也不把它当成可迁移能力
ACCOUNT_STATE_DIRS = {
    "credentials", "cookies",
}

ACCOUNT_STATE_FILE_NAMES = {
    "auth.json",
    ".credentials.json",
    ".credentials.v3.json",
    ".master.key",
    "mcp_oauth.age",
    "weflow-access-token",
    "token.json",
    "cookies",
    "cookies.json",
}

# 用户自管的敏感配置：--include-secrets 时才备份
SECRET_DIRS = {
    "secrets",
}

SECRET_FILE_NAMES = {
    ".env",
    ".netrc",
}
SECRET_FILE_PATTERNS = [
    re.compile(r"^.*\.(age|pem|p12|pfx|key|keystore)$", re.I),
]

# 运行时文件：任何级别都排除
RUNTIME_FILE_PATTERNS = [
    re.compile(r"^.*\.(sqlite|sqlite3|db|db-shm|db-wal|sqlite-shm|sqlite-wal|tmp|log|ndjson|jsonl)$", re.I),
    re.compile(r"^.*\.tmp-\d+.*$"),
    re.compile(r"^\.codex-global-state\.json.*$"),
    re.compile(r"^.*\.old-backup-\d+.*$"),      # codex memories 的轮转备份
    re.compile(r"^.*\.backup-\d+.*$"),          # config.toml.backup-*
    re.compile(r"^.*\.bak$", re.I),
    re.compile(r"^desktop_conversation_migrated$"),
    re.compile(r"^session_fragment_repair_done.*$"),
    re.compile(r"^user-state\.json$"),
    re.compile(r"^models_cache\.json$"),
    re.compile(r"^cap_sid$"),
]

# 默认（basic/advanced）全量排除集合；full / --include-secrets 会动态调整
def default_skip_dirs(include_session: bool = False, include_secrets: bool = False) -> set:
    s = set(CACHE_DIRS) | set(ACCOUNT_STATE_DIRS)
    if not include_session:
        s |= SESSION_DIRS
    if not include_secrets:
        s |= SECRET_DIRS
    return s


def is_account_state(path: Path) -> bool:
    """账号登录、Cookie 或设备绑定授权始终排除，不因加密选项而放行。"""
    if path.name.lower() in ACCOUNT_STATE_FILE_NAMES:
        return True
    return any(part.lower() in ACCOUNT_STATE_DIRS for part in path.parts)

# ---------------------------------------------------------------------------
# 密钥扫描
# ---------------------------------------------------------------------------

# 高置信密钥模式（命中即视为敏感值）
HIGH_CONFIDENCE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),                    # OpenAI 风格
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                          # AWS Access Key
    re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),                      # GitHub PAT
    re.compile(r"\bgho_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),              # Slack token
    re.compile(r"-----BEGIN [A-Z0-9 ]+PRIVATE KEY-----"),         # PEM 私钥
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),  # JWT
]

# 配置文件中敏感键名（行级/JSON 键级）
SENSITIVE_KEYS = {
    "token", "api_key", "apikey", "api-key", "access_token", "access-token",
    "secret", "secret_key", "secret-key", "password", "passwd",
    "authorization", "credential", "credentials", "client_secret",
    "client-secret", "private_key", "private-key", "bearer",
    "refresh_token", "refresh-token", "session_key", "master_key",
    "login_key", "login_password", "app_key", "app_secret", "mcp_token",
    "bot_token", "body_api_key", "food_api_key", "training_api_key",
}

# 键名以这些结尾时视为"引用型"（路径/URL/环境变量名），值非高置信密钥则不脱敏
REFERENCE_KEY_SUFFIXES = ("_file", "_path", "_dir", "_url", "_host", "_endpoint",
                          "_file_path", "_env_var", "_filename")

# 键名命中即脱敏，即使值看着无害（保守）
def key_is_sensitive(key: str) -> bool:
    k = key.strip().lower().strip("\"'")
    if k in SENSITIVE_KEYS:
        return True
    if k.endswith(REFERENCE_KEY_SUFFIXES):
        return False
    if re.search(r"(token|secret|password|api[_-]?key|access[_-]?key|authorization)", k):
        return True
    # "auth" 只匹配独立词或 auth_ 前缀，避免误伤 author/authentication 语义
    if re.match(r"^(auth|auth_|_auth|auth-)$", k):
        return True
    return False


def value_is_placeholder(value: str) -> bool:
    """${ENV_VAR}、Bearer ${ENV_VAR}、token=${ENV_VAR} 或空值视为占位符，无需脱敏。"""
    v = value.strip().strip("\"'")
    if not v:
        return True
    if re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", v):
        return True
    if re.fullmatch(r"(?i)bearer\s+\$\{[A-Za-z_][A-Za-z0-9_]*\}", v):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\$\{[A-Za-z_][A-Za-z0-9_]*\}", v):
        return True
    return False


def scan_secret_in_text(text: str) -> list[str]:
    """行级扫描，只返回模式标签；绝不把疑似敏感值原文写进 manifest。"""
    hits = []
    for line in text.splitlines():
        for index, pat in enumerate(HIGH_CONFIDENCE_PATTERNS, 1):
            if pat.search(line):
                label = f"high-confidence-pattern-{index}"
                if label not in hits:
                    hits.append(label)
                break
    return hits


def redact_json_value(value, key: str):
    """JSON 结构脱敏：键名敏感或值为高置信密钥 → 占位符。"""
    if isinstance(value, str):
        if value_is_placeholder(value):
            return value
        if key_is_sensitive(key):
            return "${" + key.upper().replace("-", "_") + "}"
        for pat in HIGH_CONFIDENCE_PATTERNS:
            if pat.search(value):
                return "${" + key.upper().replace("-", "_") + "}"
        return value
    if isinstance(value, dict):
        return {k: redact_json_value(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_json_value(v, key) for v in value]
    return value


def redact_json(text: str) -> tuple[str, list[str]]:
    """JSON 文件结构脱敏。返回 (脱敏文本, 被替换的键名列表)。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return redact_lines(text)
    replaced: list[str] = []
    before = json.dumps(data)

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, str) and not value_is_placeholder(v):
                    if key_is_sensitive(k) or any(p.search(v) for p in HIGH_CONFIDENCE_PATTERNS):
                        node[k] = "${" + k.upper().replace("-", "_") + "}"
                        if k not in replaced:
                            replaced.append(k)
                    else:
                        walk(v, k)
                elif isinstance(v, (dict, list)):
                    walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)

    walk(data)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    changed = out != before
    return out, (replaced if changed else [])


def redact_lines(text: str) -> tuple[str, list[str]]:
    """行级脱敏：敏感键名行与高置信密钥行的值 → ${KEY} 占位符。"""
    out_lines = []
    replaced: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*(.+?)\s*$", line)
        if m:
            key, raw = m.group(1), m.group(2)
            val = raw.strip().strip("\"'").strip(",")
            if not value_is_placeholder(val) and (key_is_sensitive(key) or any(p.search(val) for p in HIGH_CONFIDENCE_PATTERNS)):
                if key not in replaced:
                    replaced.append(key)
                out_lines.append(line[: m.start(2)] + "${" + key.upper().replace("-", "_") + "}")
                continue
        for pat in HIGH_CONFIDENCE_PATTERNS:
            if pat.search(line):
                out_lines.append("[REDACTED by ark] " + line.strip()[:120])
                break
        else:
            out_lines.append(line)
    changed = "\n".join(out_lines) != text
    return "\n".join(out_lines), (replaced if changed else [])


def should_redact_file(path: Path) -> bool:
    return path.suffix.lower() in {".json", ".toml", ".yaml", ".yml", ".env", ".ini", ".conf", ".cfg"}


def redact_file_content(path: Path, text: str) -> tuple[str, list[str]]:
    if path.suffix.lower() == ".json":
        return redact_json(text)
    return redact_lines(text)


# ---------------------------------------------------------------------------
# 技能识别
# ---------------------------------------------------------------------------


def parse_frontmatter(skill_md: str) -> dict:
    """解析 SKILL.md 的 YAML frontmatter（只取第一层标量键，零依赖）。"""
    meta: dict = {}
    lines = skill_md.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return meta
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[m.group(1)] = val
        elif re.match(r"^\s+[A-Za-z_]", line):
            pass  # 嵌套键：忽略（保持零依赖）
    return meta


def detect_skill(dir_path: Path) -> dict | None:
    """目录含 SKILL.md → 技能。返回技能元数据，否则 None。"""
    skill_md = dir_path / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm = parse_frontmatter(text)
    name = fm.get("name", "")
    return {
        "dirName": dir_path.name,
        "dirNameMatches": name == dir_path.name,
        "frontmatterName": name,
        "description": fm.get("description", ""),
        "license": fm.get("license", ""),
        "agentCreated": fm.get("agent_created", "").lower() == "true",
        "hasScripts": (dir_path / "scripts").is_dir(),
        "hasReferences": (dir_path / "references").is_dir(),
        "hasAssets": (dir_path / "assets").is_dir(),
        "fileCount": sum(1 for _ in dir_path.rglob("*") if _.is_file()),
    }


# ---------------------------------------------------------------------------
# 文件工具
# ---------------------------------------------------------------------------


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def is_symlink(path: Path) -> bool:
    try:
        return os.path.islink(path)
    except OSError:
        return False


def is_junction(path: Path) -> bool:
    try:
        return os.path.isjunction(path)
    except AttributeError:
        return False
    except OSError:
        return False


def link_target(path: Path) -> str | None:
    if is_symlink(path) or is_junction(path):
        try:
            return str(os.readlink(path))
        except OSError:
            return None
    return None


def file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".md", ".mdx", ".txt"}:
        return "text"
    if ext in {".py", ".js", ".ts", ".mjs", ".sh", ".ps1", ".bat", ".cjs"}:
        return "code"
    if ext in {".json", ".toml", ".yaml", ".yml", ".env", ".ini"}:
        return "config"
    return "binary"


def safe_relpath(base: Path, target: Path) -> str | None:
    """target 相对 base 的相对路径；越界返回 None。"""
    try:
        rel = target.relative_to(base)
    except ValueError:
        return None
    if rel.parts and rel.parts[0] in {"..", "."} and len(rel.parts) == 1:
        return None
    return rel.as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def size_str(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f}MB"
    return f"{n / (1024 * 1024 * 1024):.1f}GB"


def warn(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(f"[ark] {msg}", file=sys.stderr)


def info(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(f"[ark] {msg}")


def ensure_manifest_structure(manifest: dict) -> dict:
    manifest.setdefault("schemaVersion", SCHEMA_VERSION)
    manifest.setdefault("tool", {"name": TOOL_NAME, "version": TOOL_VERSION})
    manifest.setdefault("createdAt", utc_now())
    manifest.setdefault("sources", {})
    manifest.setdefault("entries", [])
    manifest.setdefault("skills", [])
    manifest.setdefault("excluded", [])
    manifest.setdefault("sanitized", [])
    manifest.setdefault("keptSecrets", [])
    manifest.setdefault("suspicious", [])
    manifest.setdefault("automations", {})
    manifest.setdefault("stats", {})
    return manifest


def extract_zip(zip_path: Path, dest: Path, password: str | None = None) -> None:
    """安全解压 zip；拒绝绝对路径、父级穿越与符号链接成员。"""
    pwd = password.encode("utf-8") if password else None
    dest_resolved = dest.resolve(strict=False)

    def validate_members(zf) -> None:
        for info in zf.infolist():
            raw = info.filename.replace("\\", "/")
            candidate = Path(raw)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError(f"zip 包含不安全路径: {info.filename}")
            target = (dest / candidate).resolve(strict=False)
            try:
                target.relative_to(dest_resolved)
            except ValueError as exc:
                raise ValueError(f"zip 成员越界: {info.filename}") from exc
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and (unix_mode & 0o170000) == 0o120000:
                raise ValueError(f"zip 包含符号链接成员: {info.filename}")

    try:
        import pyzipper  # type: ignore
        with pyzipper.AESZipFile(zip_path) as zf:
            if pwd:
                zf.setpassword(pwd)
            validate_members(zf)
            zf.extractall(dest)
    except ImportError:
        with zipfile.ZipFile(zip_path) as zf:
            validate_members(zf)
            zf.extractall(dest, pwd=pwd)


# ---------------------------------------------------------------------------
# 项目自动发现（备份前列出用过哪些项目，供用户确认/补充）
# ---------------------------------------------------------------------------


def encode_wb_project_dir(p: Path) -> str:
    """把项目路径编码为 workbuddy/projects/ 索引目录名（decode 的逆操作）。

    D:\\workspace\\project → d-workspace-project
    注意：路径段含连字符时无法精确还原，仅用于定位对应索引目录。
    """
    drive = p.drive.replace(":", "").lower()
    if not drive:
        return ""
    segs = [seg for seg in p.parts if seg not in {p.drive, p.anchor, "/", "\\"}]
    return "-".join([drive] + segs)


def decode_wb_project_dir(name: str) -> Path | None:
    """把 workbuddy/projects/ 的索引目录名解码回真实路径。

    'd-workspace-demo' → D:\\workspace\\demo
    注意：路径段本身含连字符（如 default-2026-07-20）时解码会失真，调用方需用
    exists() 验证；失真项在 --list-projects 中标为 missing，由用户补充真实路径。
    """
    if len(name) < 3 or name[1] != "-":
        return None
    drive = name[0].upper()
    if not ("A" <= drive <= "Z"):
        return None
    segs = name[2:].split("-")
    if not segs or not segs[0]:
        return None
    p = Path(f"{drive}:\\")
    for s in segs:
        p = p / s
    return p


def discover_projects(quiet: bool = False, codex_session_samples: int = 300) -> list[dict]:
    """发现用户使用过的项目文件夹（供备份前确认）。

    来源：
    1. workbuddy/projects/ 索引目录名解码（每个项目一个目录，含会话 jsonl）
    2. Codex 会话（~/.codex/sessions/**/*.jsonl）的 session_meta.payload.cwd
    返回按路径去重后的列表，每项含路径、来源、是否存在、会话/日志统计。
    """
    found: dict[str, dict] = {}

    def add(path_str: str, source: str):
        path_str = path_str.strip()
        if not path_str or path_str in {".", "C:\\", "C:/"}:
            return
        p = Path(path_str)
        key = str(p).lower().replace("/", "\\")
        if key not in found:
            found[key] = {
                "path": str(p),
                "sources": set(),
                "exists": p.is_dir(),
                "wbConversations": 0,
                "memoryLogs": 0,
                "hasAgentsMd": False,
                "hasClaudeMd": False,
                "hasWbDir": False,
            }
        found[key]["sources"].add(source)

    # 来源 1：workbuddy/projects 索引
    wb = workbuddy_home() / "projects"
    if wb.is_dir():
        for d in sorted(os.scandir(wb), key=lambda e: e.name):
            if not d.is_dir():
                continue
            decoded = decode_wb_project_dir(d.name)
            if decoded is None:
                continue
            add(str(decoded), "workbuddy-index")
            # 会话 jsonl 统计
            try:
                n = sum(1 for f in os.scandir(d.path)
                        if f.is_file() and f.name.endswith(".jsonl"))
            except OSError:
                n = 0
            if n and str(decoded).lower().replace("/", "\\") in found:
                found[str(decoded).lower().replace("/", "\\")]["wbConversations"] += n

    # 来源 2：Codex 会话 cwd
    cx_sessions = codex_home() / "sessions"
    if cx_sessions.is_dir():
        import json as _json
        n_scanned = 0
        for jf in sorted(cx_sessions.rglob("*.jsonl")):
            if n_scanned >= codex_session_samples:
                break
            try:
                with open(jf, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or '"session_meta"' not in line:
                            continue
                        rec = _json.loads(line)
                        if rec.get("type") == "session_meta":
                            cwd = (rec.get("payload") or {}).get("cwd")
                            if cwd:
                                add(cwd, "codex-session")
                            break
            except (OSError, _json.JSONDecodeError):
                continue
            n_scanned += 1

    # 存在性补充统计（真实目录存在时）
    for info in found.values():
        if not info["exists"]:
            continue
        p = Path(info["path"])
        info["hasAgentsMd"] = (p / "AGENTS.md").is_file()
        info["hasClaudeMd"] = (p / "CLAUDE.md").is_file()
        wbd = p / ".workbuddy"
        info["hasWbDir"] = wbd.is_dir()
        if wbd.is_dir():
            mem = wbd / "memory"
            if mem.is_dir():
                try:
                    info["memoryLogs"] = sum(1 for f in os.scandir(mem)
                                             if f.is_file() and f.name.endswith(".md"))
                except OSError:
                    pass

    result = []
    for info in found.values():
        info["sources"] = sorted(info["sources"])
        result.append(info)
    result.sort(key=lambda x: (not x["exists"], x["path"].lower()))
    return result
