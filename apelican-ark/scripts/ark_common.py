#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ark_common.py — 共享规则与工具：ark 备份/恢复技能（v3.2）

职责：
- 定位 Codex / WorkBuddy / Hermes 主目录（支持对应环境变量覆盖）
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
import base64
import binascii
import json
import os
import re
import sqlite3
import stat
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

SCHEMA_VERSION = "2.2"
TOOL_NAME = "ark"
TOOL_VERSION = "3.2.0"

# The only npm native credential addon Ark is allowed to rebuild. This is a
# code-owned trust anchor, not a manifest-extensible package or command list.
TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON = {
    "type": "keytar",
    "version": "7.9.0",
    "resolved": "https://registry.npmjs.org/keytar/-/keytar-7.9.0.tgz",
    "integrity": "sha512-VPD8mtVtm5JNtA2AErl6Chp06JBfy7diFQ7TQQhdpWOl6MrCRB+eRbvAZUsbGQS9kiMq0coJsy0W0vHpDCkWsQ==",
    "hasInstallScript": True,
}
TRUSTED_NODE_MCP_LAUNCH_SUFFIXES = {
    ("@softeria/ms-365-mcp-server", "0.145.2"): ("--preset", "mail,calendar"),
}
TRUSTED_EXTERNAL_TARGETS = {
    ("codex", None): "~/.codex/skills",
    ("external-root", None): "~/.agents/skills",
    ("known-portable-config", "himalaya-config"): "~/.config/himalaya",
    ("known-portable-config", "yescan-config"): "~/.yescan",
    ("known-portable-config", "opencli-config"): "~/.opencli",
    ("known-portable-config", "workbuddy-key-fallback"): "~/.workbuddy-key-fallback",
    ("portable-oauth", "opencode-auth"): "~/.local/share/opencode",
}

NPM_REGISTRY_HOST = "registry.npmjs.org"
INSTALLATION_STRATEGY_ORDER = [
    "trusted-source-when-verifiable",
    "embedded-source-fallback",
]
LOCAL_MCP_PORTABLE_STATE = {"state/managed-playlists.json"}
_PACKAGE_NAME = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)
_EXACT_VERSION = re.compile(r"^[0-9][0-9A-Za-z.!+_-]*$")
_SHA256_HASH = re.compile(r"sha256:([0-9a-fA-F]{64})")
_NPM_INTEGRITY = re.compile(r"sha512-[A-Za-z0-9+/]+={0,2}")


def is_trusted_keytar_native_credential_addon(value: object) -> bool:
    """Require the exact typed marker, including JSON scalar types and keys."""
    if type(value) is not dict:  # JSON objects decode to an exact dict here.
        return False
    expected = TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON
    if set(value) != set(expected):
        return False
    return (
        type(value.get("type")) is str and value["type"] == expected["type"]
        and type(value.get("version")) is str and value["version"] == expected["version"]
        and type(value.get("resolved")) is str and value["resolved"] == expected["resolved"]
        and type(value.get("integrity")) is str and value["integrity"] == expected["integrity"]
        and type(value.get("hasInstallScript")) is bool
        and value["hasInstallScript"] is expected["hasInstallScript"]
    )


def _hash_lock_bytes(lock_bytes: bytes) -> str:
    return hashlib.sha256(lock_bytes).hexdigest()


def parse_hash_locked_requirements(lock_bytes: bytes) -> list[dict] | None:
    """Return only exact package/version/sha256 evidence from a uv requirements lock.

    None means the file is not a self-contained hash-locked requirements file.
    An empty list is valid only for an explicitly generated, zero-dependency uv lock.
    Index/repository URLs are intentionally neither inferred nor returned.
    """
    try:
        text = lock_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    physical = text.splitlines()
    logical: list[str] = []
    current = ""
    for raw in physical:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current = (current + " " + stripped).strip()
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        logical.append(current)
        current = ""
    if current:
        logical.append(current)

    evidence: list[dict] = []
    seen: set[str] = set()
    for statement in logical:
        # The lock is executed verbatim by uv, so every installer directive is
        # part of the trust boundary.  Ark accepts package pins plus hashes
        # only; index/find-links/trusted-host/constraint options must never be
        # able to redirect restore-time resolution.
        if statement.startswith("--"):
            return None
        match = re.match(
            r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)(?:\s+(.+))?$",
            statement,
        )
        if not match or not _PACKAGE_NAME.fullmatch(match.group(1)):
            return None
        package, version, tail = match.group(1), match.group(2), match.group(3) or ""
        if not _EXACT_VERSION.fullmatch(version):
            return None
        tail_tokens = tail.split()
        if (not tail_tokens
                or any(not re.fullmatch(r"--hash=sha256:[0-9a-fA-F]{64}", token)
                       for token in tail_tokens)):
            return None
        hashes = sorted({f"sha256:{value.lower()}" for value in _SHA256_HASH.findall(tail)})
        if not hashes:
            return None
        normalized = package.lower().replace("_", "-")
        if normalized in seen:
            return None
        seen.add(normalized)
        evidence.append({
            "type": "pypi-locked-requirement",
            "package": package,
            "version": version,
            "hashes": hashes,
            "role": "locked-dependency",
        })
    if not evidence:
        lower = text.lower()
        if "autogenerated by uv" not in lower or "generate-hashes" not in lower:
            return None
    return sorted(evidence, key=lambda item: item["package"].lower())


def is_safe_npm_registry_url(value: object, package: str | None = None,
                             version: str | None = None) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    safe = (
        parsed.scheme == "https"
        and parsed.hostname == NPM_REGISTRY_HOST
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith("/")
        and parsed.path.endswith(".tgz")
    )
    if not safe or package is None or version is None:
        return safe
    package_leaf = package.rsplit("/", 1)[-1]
    return (
        parsed.path.startswith(f"/{package}/-/")
        and parsed.path.endswith(f"/{package_leaf}-{version}.tgz")
    )


def is_sha512_sri(value: object) -> bool:
    if type(value) is not str or not _NPM_INTEGRITY.fullmatch(value):
        return False
    try:
        digest = base64.b64decode(value[len("sha512-"):], validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(digest) == 64


def _npm_package_from_lock_path(lock_path: str) -> str | None:
    parts = PurePosixPath(lock_path.replace("\\", "/")).parts
    indexes = [index for index, part in enumerate(parts) if part == "node_modules"]
    if not indexes:
        return None
    tail = parts[indexes[-1] + 1:]
    if not tail:
        return None
    package = "/".join(tail[:2]) if tail[0].startswith("@") and len(tail) >= 2 else tail[0]
    return package if _PACKAGE_NAME.fullmatch(package) else None


def _npm_dependency_is_locked(packages: dict, owner_path: str, name: str) -> bool:
    """Model npm's ancestor lookup without accepting external/link fallbacks."""
    owner_parts = list(PurePosixPath(owner_path).parts) if owner_path else []
    while True:
        candidate = "/".join([*owner_parts, "node_modules", *name.split("/")])
        if candidate in packages:
            return True
        if not owner_parts:
            return False
        try:
            marker = len(owner_parts) - 1 - owner_parts[::-1].index("node_modules")
        except ValueError:
            owner_parts = []
        else:
            owner_parts = owner_parts[:marker]


def parse_npm_root_provenance(lock_bytes: bytes) -> tuple[int, list[dict]] | None:
    """Validate the complete npm v3 registry closure and return root evidence.

    npm receives the embedded lock verbatim.  Consequently every installable
    package entry must have an exact official-registry tarball and sha512 SRI;
    file/link/Git/HTTP/custom-registry and incomplete entries fail closed.
    """
    try:
        data = json.loads(lock_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (type(data) is not dict or data.get("lockfileVersion") != 3
            or "dependencies" in data):
        return None
    packages = data.get("packages")
    root = packages.get("") if type(packages) is dict else None
    if type(root) is not dict:
        return None
    root_names: set[str] = set()
    safe_root_spec = re.compile(r"[~^]?[0-9][0-9A-Za-z.*+_-]*")
    for field in ("dependencies", "optionalDependencies", "devDependencies", "peerDependencies"):
        values = root.get(field, {})
        if type(values) is not dict:
            return None
        for name, spec in values.items():
            if (type(name) is not str or not _PACKAGE_NAME.fullmatch(name)
                    or type(spec) is not str or not safe_root_spec.fullmatch(spec)):
                return None
            root_names.add(name)

    for lock_path, entry in packages.items():
        if lock_path == "":
            continue
        if (type(lock_path) is not str or type(entry) is not dict
                or entry.get("link") is True):
            return None
        package = _npm_package_from_lock_path(lock_path)
        if package is None:
            return None
        version = entry.get("version")
        resolved = entry.get("resolved")
        integrity = entry.get("integrity")
        if (
            type(version) is not str or not _EXACT_VERSION.fullmatch(version)
            or not is_safe_npm_registry_url(resolved, package, version)
            or not is_sha512_sri(integrity)
        ):
            return None
        for field in ("dependencies", "optionalDependencies"):
            dependencies = entry.get(field, {})
            if type(dependencies) is not dict:
                return None
            for name, spec in dependencies.items():
                if (type(name) is not str or not _PACKAGE_NAME.fullmatch(name)
                        or type(spec) is not str or not spec
                        or not _npm_dependency_is_locked(packages, lock_path, name)):
                    return None
        peers = entry.get("peerDependencies", {})
        peer_meta = entry.get("peerDependenciesMeta", {})
        if type(peers) is not dict or type(peer_meta) is not dict:
            return None
        for name, spec in peers.items():
            meta = peer_meta.get(name, {})
            optional = type(meta) is dict and meta.get("optional") is True
            if (type(name) is not str or not _PACKAGE_NAME.fullmatch(name)
                    or type(spec) is not str or not spec
                    or (not optional and not _npm_dependency_is_locked(
                        packages, lock_path, name
                    ))):
                return None

    evidence: list[dict] = []
    for name in sorted(root_names, key=str.lower):
        entry = packages.get(f"node_modules/{name}")
        if type(entry) is not dict:
            return None
        version = entry.get("version")
        resolved = entry.get("resolved")
        integrity = entry.get("integrity")
        if (
            type(version) is not str or not _EXACT_VERSION.fullmatch(version)
            or not is_safe_npm_registry_url(resolved, name, version)
            or not is_sha512_sri(integrity)
        ):
            return None
        evidence.append({
            "type": "npm-registry-root-dependency",
            "package": name,
            "version": version,
            "resolved": resolved,
            "integrity": integrity,
            "role": "root-dependency",
        })
    return data["lockfileVersion"], evidence


def derive_keytar_native_credential_addon(lock_bytes: bytes) -> tuple[dict | None, str | None]:
    """Re-derive the sole audited native addon marker from an embedded lock."""
    try:
        data = json.loads(lock_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"could not parse root npm lock JSON: {exc}"
    packages = data.get("packages") if type(data) is dict else None
    if type(packages) is not dict:
        return None, "root npm lock has no packages object"
    if "node_modules/keytar" not in packages:
        return None, None
    entry = packages.get("node_modules/keytar")
    if type(entry) is not dict:
        return None, "node_modules/keytar lock entry is not an object"
    candidate = {
        "type": "keytar",
        "version": entry.get("version"),
        "resolved": entry.get("resolved"),
        "integrity": entry.get("integrity"),
        "hasInstallScript": entry.get("hasInstallScript"),
    }
    if is_trusted_keytar_native_credential_addon(candidate):
        return dict(TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON), None
    return None, "node_modules/keytar differs from the audited keytar 7.9.0 registry trust anchor"


def _node_entry_package(item: dict) -> str | None:
    recipe = item.get("runtimeRecipe") if type(item.get("runtimeRecipe")) is dict else {}
    verification = recipe.get("verification") if type(recipe.get("verification")) is dict else {}
    index = verification.get("argIndex")
    if type(index) is not int:
        return None
    rewrites = item.get("argsPathRewrites") if type(item.get("argsPathRewrites")) is list else []
    relative = next((entry.get("relativePath") for entry in rewrites
                     if type(entry) is dict and entry.get("index") == index), None)
    if type(relative) is not str:
        return None
    parts = Path(relative.replace("\\", "/")).parts
    try:
        marker = parts.index("node_modules")
    except ValueError:
        return None
    tail = parts[marker + 1:]
    if not tail:
        return None
    package = "/".join(tail[:2]) if tail[0].startswith("@") and len(tail) >= 2 else tail[0]
    return package if _PACKAGE_NAME.fullmatch(package) else None


def node_package_from_entry_arg(value: str) -> str | None:
    """Extract an npm package name from an absolute node_modules entry path."""
    normalized = str(value).replace("\\", "/")
    marker = "/node_modules/"
    if marker not in normalized:
        return None
    tail = normalized.rsplit(marker, 1)[1].strip("/").split("/")
    if not tail or not tail[0]:
        return None
    package = "/".join(tail[:2]) if tail[0].startswith("@") and len(tail) >= 2 else tail[0]
    return package if _PACKAGE_NAME.fullmatch(package) else None


def trusted_node_launch_suffix(package: str | None, version: str | None,
                               suffix: list[str] | tuple[str, ...]) -> bool:
    if not suffix:
        return True
    expected = TRUSTED_NODE_MCP_LAUNCH_SUFFIXES.get((str(package), str(version)))
    return expected is not None and tuple(suffix) == expected


def node_item_has_trusted_launch_args(item: dict) -> bool:
    args = item.get("argsTemplate") if type(item.get("argsTemplate")) is list else []
    if not args:
        return False
    package = _node_entry_package(item)
    installation = item.get("installation") if type(item.get("installation")) is dict else {}
    provenance = installation.get("packageProvenance")
    evidence = next(
        (entry for entry in provenance
         if type(entry) is dict and entry.get("package") == package), None
    ) if type(provenance) is list else None
    return trusted_node_launch_suffix(
        package, evidence.get("version") if evidence else None, args[1:]
    )


def external_target_template_is_trusted(item: dict) -> bool:
    key = (item.get("includedBy"), item.get("configClass"))
    return (
        item.get("requiresExplicitMapping") is False
        and item.get("targetTemplate") == TRUSTED_EXTERNAL_TARGETS.get(key)
    )


def local_auto_target_is_trusted(target: object) -> bool:
    if type(target) is not dict or target.get("requiresExplicitMapping") is not False:
        return False
    relative = target.get("relativePath")
    if type(relative) is not str:
        return False
    parts = PurePosixPath(relative.replace("\\", "/")).parts
    if not parts or ".." in parts:
        return False
    if target.get("kind") == "localappdata":
        return True
    return target.get("kind") == "home" and len(parts) > 2 and parts[:2] == (".local", "share")


def general_home_link_target_is_trusted(relative: Path) -> bool:
    """Allow legacy absolute links only inside known skill stores."""
    parts = tuple(part.casefold() for part in relative.parts)
    prefixes = (
        (".codex", "skills"),
        (".agents", "skills"),
        (".workbuddy", "skills"),
        ("appdata", "local", "hermes", "skills"),
        ("appdata", "local", "hermes", "profiles"),
    )
    return any(len(parts) >= len(prefix) and parts[:len(prefix)] == prefix for prefix in prefixes)


def build_local_mcp_installation(item: dict, lock_bytes: bytes) -> dict:
    """Derive non-executable hybrid installation data from typed item + lock."""
    recipe = item["runtimeRecipe"]
    recipe_type = recipe["type"]
    lock_path = recipe["lockFile"]
    provenance: list[dict]
    trusted_source = None
    if recipe_type == "python-uv-lock":
        parsed = parse_hash_locked_requirements(lock_bytes)
        if parsed is None:
            raise ValueError("requirements lock is not exact and hash-locked")
        provenance = parsed
        runtime = {
            "name": "python", "version": "3.11", "packageManager": "uv",
            "recipeType": "python-uv-lock",
        }
        lock = {
            "type": "uv-hash-locked-requirements", "path": lock_path,
            "sha256": _hash_lock_bytes(lock_bytes), "hashMode": "require-hashes",
        }
    elif recipe_type == "node-npm-lock":
        parsed = parse_npm_root_provenance(lock_bytes)
        if parsed is None:
            raise ValueError("npm lock is not a supported package lock")
        lockfile_version, provenance = parsed
        entry_package = _node_entry_package(item)
        entry_evidence = next(
            (entry for entry in provenance if entry["package"] == entry_package), None
        )
        if entry_evidence is not None:
            trusted_source = {
                "type": "npm-registry-entry-package",
                "registryHost": NPM_REGISTRY_HOST,
                "package": dict(entry_evidence),
            }
        runtime = {
            "name": "node", "packageManager": "npm", "recipeType": "node-npm-lock",
        }
        lock = {
            "type": "npm-package-lock", "path": lock_path,
            "sha256": _hash_lock_bytes(lock_bytes), "lockfileVersion": lockfile_version,
        }
    else:
        raise ValueError(f"unsupported local MCP recipe: {recipe_type}")
    target = item["target"]
    return {
        "type": "hybrid-portable-v1",
        "nonExecutable": True,
        "target": {
            "mappingId": item["id"],
            "kind": target["kind"],
            "relativePath": target.get("relativePath"),
            "requiresExplicitMapping": target["requiresExplicitMapping"],
        },
        "strategyOrder": list(INSTALLATION_STRATEGY_ORDER),
        "trustedSource": trusted_source,
        "embeddedSourceFallback": {
            "type": "ark-archive-source",
            "archivePrefix": item["archivePrefix"],
            "lockFile": lock_path,
            "role": "custom-project-source",
        },
        "runtime": runtime,
        "lock": lock,
        "packageProvenance": provenance,
        "healthCheck": dict(recipe["verification"]),
        "reauthorization": "required",
    }

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


def hermes_home() -> Path:
    """Hermes 用户数据根；Windows 原生安装与 Unix 默认布局不同。"""
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "hermes"
        return home_dir() / "AppData" / "Local" / "hermes"
    return home_dir() / ".hermes"


def hermes_home_for_user(user_home: Path) -> Path:
    """把当前操作系统的 Hermes 默认布局映射到指定用户主目录。"""
    if os.name == "nt":
        return user_home / "AppData" / "Local" / "hermes"
    return user_home / ".hermes"


def hermes_desktop_home() -> Path:
    """Electron userData；它与 HERMES_HOME 是两个独立的状态根。"""
    override = os.environ.get("HERMES_DESKTOP_USER_DATA")
    if override:
        return Path(override)
    if os.name == "nt":
        roaming = os.environ.get("APPDATA")
        return (Path(roaming) if roaming else home_dir() / "AppData" / "Roaming") / "Hermes"
    if sys.platform == "darwin":
        return home_dir() / "Library" / "Application Support" / "Hermes"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else home_dir() / ".config") / "Hermes"


def hermes_desktop_home_for_user(user_home: Path, platform_name: str | None = None) -> Path:
    platform_name = platform_name or ("windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux"))
    if platform_name == "windows":
        return user_home / "AppData" / "Roaming" / "Hermes"
    if platform_name == "macos":
        return user_home / "Library" / "Application Support" / "Hermes"
    return user_home / ".config" / "Hermes"


def memory_tencentdb_root() -> Path:
    env = os.environ.get("MEMORY_TENCENTDB_ROOT")
    return Path(env) if env else home_dir() / ".memory-tencentdb"


# ---------------------------------------------------------------------------
# 排除清单：按"任何级别 / 会话类 / 密钥类"三档拆分
# - CACHE_DIRS：任何备份级别都排除（缓存、临时、日志、可重建）
# - SESSION_DIRS：basic/advanced 排除，--profile full 时放行（对话历史）
# - ACCOUNT_STATE_*：账号登录、Cookie、设备绑定授权；任何级别都排除
# - SECRET_DIRS / SECRET_FILES：用户自管的敏感配置；仅单独确认后进入 AES 包
# ---------------------------------------------------------------------------

CACHE_DIRS = {
    ".git", ".tmp", ".sandbox", ".sandbox-bin", ".sandbox-secrets",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    ".venv", "venv", ".runtime", "site-packages",
    "logs", "cache", "blobs", "traces", "tasks", "plans", "teams",
    "app", "vendor", "binaries", "local_storage", "pending-telemetry",
    "audit-log", "artifact-index", "clipboard-images", "shell-snapshots",
    "file-history", "plugin-marketplace-state", "plugin-marketplace-state-new",
    "claw-state", ".workbuddy-sqlite-migrations", "backups",
    "automation-backups", "extensions", "mcp-oauth-locks",
    "connectors-marketplace", "node_modules",
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
    # Process locks only. Do not blanket-match *.lock: requirements.lock,
    # uv.lock and poetry.lock are deterministic reconstruction inputs.
    re.compile(r"^(?:\..+\.lock|lock|lockfile|.*\.pid)$", re.I),
    re.compile(r"^.*\.tmp-\d+.*$"),
    re.compile(r"^\.codex-global-state\.json.*$"),
    re.compile(r"^.*\.old-backup-\d+.*$"),      # codex memories 的轮转备份
    re.compile(r"^.*\.backup-\d+.*$"),          # config.toml.backup-*
    re.compile(r"^.*\.bak$", re.I),
    re.compile(r"^desktop_conversation_migrated$"),
    re.compile(r"^session_fragment_repair_done.*$"),
    re.compile(r"^user-state\.json$"),
    re.compile(r"^models_cache\.json$"),
    re.compile(r"^ticker_(?:heartbeat|last_success)$"),
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

def scan_secret_in_file(path: Path, chunk_size: int = 1 << 20) -> list[str]:
    """Streaming scan for large text/config files without loading them whole."""
    hits: list[str] = []
    carry = ""
    assignment = re.compile(
        r"(?im)^\s*[A-Za-z_][A-Za-z0-9_.-]*(?:token|secret|password|api[_-]?key|authorization)"
        r"[A-Za-z0-9_.-]*\s*[:=]\s*\S+"
    )
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                text = carry + chunk.decode("utf-8", errors="ignore")
                for label in scan_secret_in_text(text):
                    if label not in hits:
                        hits.append(label)
                if assignment.search(text) and "sensitive-assignment" not in hits:
                    hits.append("sensitive-assignment")
                carry = text[-4096:]
    except OSError:
        return ["unreadable-large-file"]
    return hits


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
            for index, item in enumerate(list(node)):
                if isinstance(item, str) and not value_is_placeholder(item):
                    if any(p.search(item) for p in HIGH_CONFIDENCE_PATTERNS):
                        node[index] = "${REDACTED_VALUE}"
                        if "high-confidence-value" not in replaced:
                            replaced.append("high-confidence-value")
                elif isinstance(item, (dict, list)):
                    walk(item, key)

    if isinstance(data, str) and not value_is_placeholder(data):
        if any(p.search(data) for p in HIGH_CONFIDENCE_PATTERNS):
            data = "${REDACTED_VALUE}"
            replaced.append("high-confidence-value")
    else:
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
                # 绝不把命中行的任何原文带入脱敏副本。旧实现拼接前 120 字符，
                # 在密钥位于自由文本行时会直接泄露全部或部分凭据。
                label = "high-confidence-value"
                if label not in replaced:
                    replaced.append(label)
                out_lines.append("[REDACTED by ark: high-confidence-value]")
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
    """目录含大小写完全匹配的 SKILL.md → 技能。"""
    try:
        actual = next((entry for entry in os.scandir(dir_path)
                       if entry.is_file() and entry.name == "SKILL.md"), None)
    except OSError:
        return None
    if actual is None:
        return None
    skill_md = Path(actual.path)
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
        checker = getattr(os.path, "isjunction", None)
        if checker is not None:
            return bool(checker(path))
        # Python 3.11 on Windows has no os.path.isjunction, but exposes the
        # reparse-point file attribute. A directory reparse point that is not
        # a symlink is a junction for Ark topology purposes.
        attrs = path.lstat().st_file_attributes
        return (bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
                and bool(attrs & stat.FILE_ATTRIBUTE_DIRECTORY)
                and not is_symlink(path))
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


def is_link_like(path: Path) -> bool:
    """True for symlinks and Windows junctions without following the target."""
    return is_symlink(path) or is_junction(path)


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
    manifest.setdefault("artifactClasses", {})
    manifest.setdefault("externalRoots", [])
    manifest.setdefault("links", [])
    manifest.setdefault("softwareInventory", [])
    manifest.setdefault("projectMappings", [])
    manifest.setdefault("localMcpProjects", [])
    manifest.setdefault("postRestoreActions", [])
    manifest.setdefault("coverageGaps", [])
    manifest.setdefault("environmentRequirements", [])
    manifest.setdefault("stats", {})
    return manifest


def sqlite_readonly(path: Path, immutable: bool = False) -> sqlite3.Connection:
    """Open an existing SQLite database without creating it or its sidecars."""
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = "file:" + path.resolve().as_posix() + ("?immutable=1" if immutable else "?mode=ro")
    return sqlite3.connect(uri, uri=True, timeout=5)


def hermes_project_folders(db: Path) -> list[dict]:
    """Read projects.db mappings. immutable avoids touching a live DB's WAL/SHM."""
    result: list[dict] = []
    try:
        con = sqlite_readonly(db, immutable=True)
        projects = {
            row[0]: {"id": row[0], "name": row[1], "archived": bool(row[2])}
            for row in con.execute("SELECT id, name, archived FROM projects")
        }
        for project_id, path, label, is_primary in con.execute(
                "SELECT project_id, path, label, is_primary FROM project_folders"):
            item = dict(projects.get(project_id, {"id": project_id, "name": project_id, "archived": False}))
            item.update({"path": str(path), "label": label, "isPrimary": bool(is_primary)})
            result.append(item)
        con.close()
    except (OSError, sqlite3.Error):
        return []
    return result


def directory_lock_status(lock_path: Path) -> dict:
    """Best-effort, read-only live-lock probe for Electron/LevelDB stores."""
    status = {"path": str(lock_path), "exists": lock_path.exists(), "exclusiveRead": None}
    if not lock_path.exists():
        return status
    if os.name != "nt":
        # Presence is still reported; portable POSIX locking semantics differ.
        return status
    try:
        import ctypes
        from ctypes import wintypes
        handle = ctypes.windll.kernel32.CreateFileW(
            str(lock_path), 0x80000000, 0, None, 3, 0x80, None
        )
        invalid = wintypes.HANDLE(-1).value
        if handle == invalid:
            status["exclusiveRead"] = False
        else:
            status["exclusiveRead"] = True
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        status["exclusiveRead"] = None
    return status


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

    C:\\Users\\example\\Desktop\\project → c-Users-example-Desktop-project
    注意：路径段含连字符时无法精确还原，仅用于定位对应索引目录。
    """
    drive = p.drive.replace(":", "").lower()
    if not drive:
        return ""
    segs = [seg for seg in p.parts if seg not in {p.drive, p.anchor, "/", "\\"}]
    return "-".join([drive] + segs)


def decode_wb_project_dir(name: str) -> Path | None:
    """把 workbuddy/projects/ 的索引目录名解码回真实路径。

    'c-Users-example-Documents-Projects-demo' → C:\\Users\\example\\Documents\\Projects\\demo
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
