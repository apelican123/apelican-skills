#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方舟恢复工具 v3.2：默认只读，支持 schema 2.2 local stdio MCP 重建。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ark_common as C

SUPPORTED_SCHEMAS = {"1.0", "2.0", "2.1", "2.2"}
VALID_PARTS = {
    "codex", "workbuddy", "hermes", "hermes-memory", "hermes-desktop",
    "hermes-provider", "external-roots", "projects", "local-mcp-projects",
}
PATH_CONFIG_NAMES = {
    "config.toml", "config.yaml", ".env", "tdai-gateway.standalone.yaml",
    "mcp.json", "settings.json", "models.json",
    "automation.toml", "automations.json", "hooks.json", "keybindings.json",
    "jobs.json", "profile.yaml", "webhook_subscriptions.json", ".ark-portable-environment.env",
}
COMPLETE_NONBLOCKING_GAP_CLASSES = {"desktop-userdata-missing"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_PACKAGE = re.compile(r"^(?:@[A-Za-z0-9][A-Za-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]*$")
SAFE_VERSION = re.compile(r"^[0-9][0-9A-Za-z.!+_-]*$")
SHA256_EVIDENCE = re.compile(r"sha256:[0-9a-f]{64}")


def resolve_password(opts) -> str | None:
    choices = [bool(opts.zip_password), bool(opts.password_file), bool(opts.password_env), bool(opts.prompt_password)]
    if sum(choices) > 1:
        raise SystemExit("--zip-password、--password-file、--password-env 只能使用一种")
    if opts.zip_password:
        C.warn("--zip-password 可能进入进程参数或历史；建议改用 --password-env 或隐藏输入。")
        return opts.zip_password
    if opts.password_file:
        path = Path(opts.password_file).expanduser()
        if not path.is_file():
            raise SystemExit(f"口令文件不存在: {path}")
        return path.read_text(encoding="utf-8").rstrip("\r\n")
    if opts.password_env:
        value = os.environ.get(opts.password_env)
        if not value:
            raise SystemExit(f"环境变量 {opts.password_env} 未设置或为空")
        return value
    if opts.prompt_password:
        return getpass.getpass("方舟备份口令: ")
    return None


class BackupReader:
    """读取目录或 ZIP；ZIP 不解压到临时目录。"""

    def __init__(self, arg: str, password: str | None):
        self.path = Path(arg).expanduser()
        self.root: Path | None = None
        self.zf = None
        self.prefix = ""
        self.password = password.encode("utf-8") if password else None
        if self.path.is_dir():
            self.root = self.path.resolve()
            return
        if not (self.path.is_file() and self.path.suffix.lower() == ".zip"):
            raise SystemExit(f"备份不存在: {self.path}")
        try:
            import pyzipper  # type: ignore
            self.zf = pyzipper.AESZipFile(self.path)
        except ImportError:
            self.zf = zipfile.ZipFile(self.path)
        if self.password:
            self.zf.setpassword(self.password)
        names = []
        for info in self.zf.infolist():
            raw = info.filename.replace("\\", "/")
            pure = PurePosixPath(raw)
            if pure.is_absolute() or ".." in pure.parts:
                raise SystemExit(f"ZIP 包含不安全路径: {info.filename}")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and (mode & 0o170000) == 0o120000:
                raise SystemExit(f"ZIP 包含符号链接成员: {info.filename}")
            names.append(raw)
        if names.count("manifest.json") == 1:
            self.prefix = ""
        else:
            # Wrapped archives may use `<folder>/manifest.json`. Nested skills
            # and plugins are allowed to carry their own manifest.json; they are
            # data, not candidate Ark roots.
            wrapped = []
            for name in names:
                pure = PurePosixPath(name)
                if len(pure.parts) == 2 and pure.name == "manifest.json":
                    prefix = pure.parts[0] + "/"
                    if all(item.startswith(prefix) for item in names):
                        wrapped.append(prefix)
            if len(set(wrapped)) != 1:
                raise SystemExit(
                    "ZIP 中缺少唯一的根 manifest.json（嵌套技能 manifest 不计入）"
                )
            self.prefix = wrapped[0]

    def _member(self, rel: str) -> str:
        pure = PurePosixPath(rel.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"不安全的包内路径: {rel}")
        return self.prefix + pure.as_posix()

    def exists(self, rel: str) -> bool:
        if self.root is not None:
            path = (self.root / Path(*PurePosixPath(rel).parts)).resolve(strict=False)
            try:
                path.relative_to(self.root)
            except ValueError:
                return False
            return path.is_file()
        try:
            self.zf.getinfo(self._member(rel))
            return True
        except KeyError:
            return False

    def open(self, rel: str):
        if self.root is not None:
            path = (self.root / Path(*PurePosixPath(rel).parts)).resolve(strict=False)
            try:
                path.relative_to(self.root)
            except ValueError as exc:
                raise ValueError(f"包内路径越界: {rel}") from exc
            return path.open("rb")
        try:
            return self.zf.open(self._member(rel), "r", pwd=self.password)
        except (RuntimeError, NotImplementedError) as exc:
            raise SystemExit("无法解密备份：请安装 pyzipper 并提供正确口令。") from exc

    def read_json(self, rel: str):
        with self.open(rel) as stream:
            return json.loads(stream.read().decode("utf-8"))

    def copy_to(self, rel: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.open(rel) as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=1 << 20)

    def close(self) -> None:
        if self.zf is not None:
            self.zf.close()


def _safe_posix_rel(value: object, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, str):
        return False
    if value in {"", "."}:
        return allow_empty
    pure = PurePosixPath(value.replace("\\", "/"))
    return not pure.is_absolute() and ".." not in pure.parts and bool(pure.parts)


def _safe_single_segment(value: object) -> bool:
    if type(value) is not str or not value or len(value) > 128:
        return False
    pure = PurePosixPath(value.replace("\\", "/"))
    return (len(pure.parts) == 1 and pure.parts[0] not in {".", ".."}
            and not any(ord(char) < 32 for char in value))


def _looks_absolute_portable_path(value: object) -> bool:
    if type(value) is not str or not value or any(ord(char) < 32 for char in value):
        return False
    normalized = value.replace("\\", "/")
    return (PurePosixPath(normalized).is_absolute()
            or bool(re.match(r"^[A-Za-z]:/", normalized))
            or normalized.startswith("//"))


def _typed_local_mcp_args(item: dict, root: Path) -> list[str]:
    """Construct executable args from the code-owned recipe, never manifest text."""
    recipe = item["runtimeRecipe"]
    if recipe["type"] == "python-uv-lock":
        return ["-m", recipe["verification"]["module"]]
    rewrite = item["argsPathRewrites"][0]
    if not C.node_item_has_trusted_launch_args(item):
        raise SystemExit(f"manifest local MCP Node args 未满足 typed contract: {item.get('id')}")
    entry = str(root / Path(*PurePosixPath(rewrite["relativePath"]).parts))
    # The suffix is accepted only after exact package/version allowlist
    # validation; arbitrary manifest arguments never reach this branch.
    return [entry, *item["argsTemplate"][1:]]


def _exact_object(value: object, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise SystemExit(f"manifest {label} 字段非法")
    return value


def _validate_package_evidence(value: object, item_id: str) -> None:
    if type(value) is not dict:
        raise SystemExit(f"manifest local MCP package provenance 类型非法: {item_id}")
    evidence_type = value.get("type")
    if evidence_type == "pypi-locked-requirement":
        _exact_object(value, {"type", "package", "version", "hashes", "role"},
                      f"local MCP Python package provenance: {item_id}")
        hashes = value.get("hashes")
        if (value.get("role") != "locked-dependency"
                or type(value.get("package")) is not str
                or not SAFE_PACKAGE.fullmatch(value["package"])
                or type(value.get("version")) is not str
                or not SAFE_VERSION.fullmatch(value["version"])
                or type(hashes) is not list or not hashes
                or hashes != sorted(set(hashes))
                or not all(type(item) is str and SHA256_EVIDENCE.fullmatch(item) for item in hashes)):
            raise SystemExit(f"manifest local MCP Python package provenance 非法: {item_id}")
    elif evidence_type == "npm-registry-root-dependency":
        _exact_object(value, {"type", "package", "version", "resolved", "integrity", "role"},
                      f"local MCP npm package provenance: {item_id}")
        if (value.get("role") != "root-dependency"
                or type(value.get("package")) is not str
                or not SAFE_PACKAGE.fullmatch(value["package"])
                or type(value.get("version")) is not str
                or not SAFE_VERSION.fullmatch(value["version"])
                or not C.is_safe_npm_registry_url(
                    value.get("resolved"), value.get("package"), value.get("version")
                )
                or not C.is_sha512_sri(value.get("integrity"))):
            raise SystemExit(f"manifest local MCP npm package provenance 非法: {item_id}")
    else:
        raise SystemExit(f"manifest local MCP package provenance 类型未允许: {item_id}")


def _validate_installation(item: dict, item_id: str) -> None:
    installation = _exact_object(
        item.get("installation"),
        {
            "type", "nonExecutable", "target", "strategyOrder", "trustedSource",
            "embeddedSourceFallback", "runtime", "lock", "packageProvenance",
            "healthCheck", "reauthorization",
        },
        f"local MCP installation: {item_id}",
    )
    if (installation.get("type") != "hybrid-portable-v1"
            or installation.get("nonExecutable") is not True
            or installation.get("strategyOrder") != C.INSTALLATION_STRATEGY_ORDER
            or installation.get("reauthorization") != "required"):
        raise SystemExit(f"manifest local MCP installation contract 非法: {item_id}")

    target = item["target"]
    install_target = _exact_object(
        installation.get("target"),
        {"mappingId", "kind", "relativePath", "requiresExplicitMapping"},
        f"local MCP installation target: {item_id}",
    )
    expected_target = {
        "mappingId": item_id,
        "kind": target.get("kind"),
        "relativePath": target.get("relativePath"),
        "requiresExplicitMapping": target.get("requiresExplicitMapping"),
    }
    if install_target != expected_target:
        raise SystemExit(f"manifest local MCP installation target 不匹配: {item_id}")

    recipe = item["runtimeRecipe"]
    fallback = _exact_object(
        installation.get("embeddedSourceFallback"),
        {"type", "archivePrefix", "lockFile", "role"},
        f"local MCP embedded fallback: {item_id}",
    )
    if fallback != {
        "type": "ark-archive-source",
        "archivePrefix": item["archivePrefix"],
        "lockFile": recipe["lockFile"],
        "role": "custom-project-source",
    }:
        raise SystemExit(f"manifest local MCP embedded fallback 不匹配: {item_id}")

    runtime = installation.get("runtime")
    lock = installation.get("lock")
    health = installation.get("healthCheck")
    if recipe["type"] == "python-uv-lock":
        _exact_object(runtime, {"name", "version", "packageManager", "recipeType"},
                      f"local MCP Python runtime: {item_id}")
        _exact_object(lock, {"type", "path", "sha256", "hashMode"},
                      f"local MCP Python lock: {item_id}")
        if runtime != {
            "name": "python", "version": "3.11", "packageManager": "uv",
            "recipeType": "python-uv-lock",
        } or lock.get("type") != "uv-hash-locked-requirements" or lock.get("hashMode") != "require-hashes":
            raise SystemExit(f"manifest local MCP Python installation 非法: {item_id}")
    else:
        _exact_object(runtime, {"name", "packageManager", "recipeType"},
                      f"local MCP Node runtime: {item_id}")
        _exact_object(lock, {"type", "path", "sha256", "lockfileVersion"},
                      f"local MCP Node lock: {item_id}")
        if runtime != {
            "name": "node", "packageManager": "npm", "recipeType": "node-npm-lock",
        } or lock.get("type") != "npm-package-lock" or type(lock.get("lockfileVersion")) is not int:
            raise SystemExit(f"manifest local MCP Node installation 非法: {item_id}")
    if (lock.get("path") != recipe["lockFile"]
            or type(lock.get("sha256")) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", lock["sha256"])
            or health != recipe["verification"]):
        raise SystemExit(f"manifest local MCP installation lock/health evidence 不匹配: {item_id}")

    provenance = installation.get("packageProvenance")
    if type(provenance) is not list:
        raise SystemExit(f"manifest local MCP packageProvenance 类型非法: {item_id}")
    for evidence in provenance:
        _validate_package_evidence(evidence, item_id)
    if len({(item["type"], item["package"]) for item in provenance}) != len(provenance):
        raise SystemExit(f"manifest local MCP packageProvenance 重复: {item_id}")
    if recipe["type"] == "python-uv-lock" and any(
            evidence.get("type") != "pypi-locked-requirement" for evidence in provenance):
        raise SystemExit(f"manifest local MCP Python provenance 混入非 Python 类型: {item_id}")
    if recipe["type"] == "node-npm-lock" and any(
            evidence.get("type") != "npm-registry-root-dependency" for evidence in provenance):
        raise SystemExit(f"manifest local MCP Node provenance 混入非 npm 类型: {item_id}")

    trusted = installation.get("trustedSource")
    if trusted is not None:
        _exact_object(trusted, {"type", "registryHost", "package"},
                      f"local MCP trustedSource: {item_id}")
        if (recipe["type"] != "node-npm-lock"
                or trusted.get("type") != "npm-registry-entry-package"
                or trusted.get("registryHost") != C.NPM_REGISTRY_HOST):
            raise SystemExit(f"manifest local MCP trustedSource 非法: {item_id}")
        _validate_package_evidence(trusted.get("package"), item_id)
        if trusted["package"] not in provenance:
            raise SystemExit(f"manifest local MCP trustedSource 无对应 lock provenance: {item_id}")


def validate_installation_evidence(reader: BackupReader, manifest: dict) -> None:
    """Re-derive installation metadata from embedded locks before any restore."""
    if str(manifest.get("schemaVersion")) != "2.2":
        return
    entry_map = {entry.get("relPath"): entry for entry in manifest.get("entries", [])
                 if type(entry) is dict}
    for item in manifest.get("localMcpProjects", []):
        item_id = item["id"]
        lock_rel = f"{item['archivePrefix']}/{item['runtimeRecipe']['lockFile']}"
        lock_entry = entry_map.get(lock_rel)
        if type(lock_entry) is not dict or not reader.exists(lock_rel):
            raise SystemExit(f"manifest local MCP installation lock 缺失: {item_id}/{lock_rel}")
        try:
            with reader.open(lock_rel) as stream:
                lock_bytes = stream.read()
            expected = C.build_local_mcp_installation(item, lock_bytes)
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"manifest local MCP installation lock 无法验证: {item_id}: {exc}") from exc
        if lock_entry.get("sha256") != hashlib.sha256(lock_bytes).hexdigest():
            raise SystemExit(f"manifest local MCP installation lock hash 不匹配: {item_id}")
        if item["installation"] != expected:
            raise SystemExit(f"manifest local MCP installation 与包内 lock evidence 不一致: {item_id}")
        if item["runtimeRecipe"]["type"] == "node-npm-lock":
            derived_addon, addon_gap = C.derive_keytar_native_credential_addon(lock_bytes)
            declared_addon = item["runtimeRecipe"].get("nativeCredentialAddon")
            if addon_gap is not None:
                raise SystemExit(
                    f"manifest local MCP keytar lock trust anchor 无法验证: {item_id}: {addon_gap}"
                )
            if declared_addon != derived_addon:
                raise SystemExit(
                    f"manifest local MCP native credential addon 与包内 lock 不匹配: {item_id}"
                )


_FIXED_POST_RESTORE_ACTIONS = {
    "validate-portable-oauth": {
        "id": "validate-portable-oauth", "required": True,
        "action": "Test restored OAuth tokens; if refresh fails, run provider reauthorization without overwriting newer target credentials.",
    },
    "verify-memory-tencentdb-provider": {
        "id": "verify-memory-tencentdb-provider", "required": True,
        "action": "run provider discovery and memory health checks",
        "commands": ["hermes plugins", "hermes memory status", "hermes doctor"],
    },
    "install-platform-runtime": {
        "id": "install-platform-runtime", "required": True,
        "action": "Install Hermes for the target OS from the official installer; do not copy venv/node_modules.",
    },
    "reauthorize-accounts": {
        "id": "reauthorize-accounts", "required": True,
        "action": "Reauthorize MCP OAuth, messaging accounts, desktop connection token, cookies and device OAuth.",
    },
    "health-check": {
        "id": "health-check", "required": True,
        "action": "Run hermes doctor, hermes mcp list/test, cron inspection, provider discovery and memory recall/write.",
    },
}


def _validate_post_restore_actions(manifest: dict) -> None:
    """Accept only code-owned advisory actions; none are executable payloads."""
    allowed = dict(_FIXED_POST_RESTORE_ACTIONS)
    for local in manifest.get("localMcpProjects", []):
        item_id = local["id"]
        action_id = f"reauthorize-local-mcp-{item_id}"
        allowed[action_id] = {
            "id": action_id, "required": True,
            "action": (
                f"Reauthorize Hermes MCP {local['profile']}/{local['server']} on the target device; "
                "code health is verified separately."
            ),
        }
    seen: set[str] = set()
    for item in manifest.get("postRestoreActions", []):
        if type(item) is not dict or type(item.get("id")) is not str:
            raise SystemExit("manifest postRestoreActions 类型非法")
        action_id = item["id"]
        if action_id in seen or item != allowed.get(action_id):
            raise SystemExit(f"manifest postRestoreActions 未在代码 allowlist 或内容不匹配: {action_id!r}")
        seen.add(action_id)


def validate_manifest(manifest: dict) -> None:
    schema = str(manifest.get("schemaVersion", ""))
    if schema not in SUPPORTED_SCHEMAS:
        raise SystemExit(f"不支持的 schema: {schema}")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("manifest.entries 缺失或类型错误")
    seen = set()
    for entry in entries:
        rel = str(entry.get("relPath", "")).replace("\\", "/")
        pure = PurePosixPath(rel)
        if not pure.parts or pure.is_absolute() or ".." in pure.parts:
            raise SystemExit(f"manifest 包含不安全路径: {rel}")
        if pure.parts[0] not in VALID_PARTS:
            raise SystemExit(f"manifest 包含未知顶层范围: {rel}")
        if rel in seen:
            raise SystemExit(f"manifest 包含重复路径: {rel}")
        seen.add(rel)
        digest = entry.get("sha256")
        if digest is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
            raise SystemExit(f"manifest hash 格式错误: {rel}")
        if schema in {"2.1", "2.2"} and not entry.get("artifactClass"):
            raise SystemExit(f"schema {schema} entry 缺少 artifactClass: {rel}")
    if schema in {"2.1", "2.2"}:
        for name in ("externalRoots", "links", "softwareInventory", "projectMappings",
                     "postRestoreActions", "coverageGaps"):
            if not isinstance(manifest.get(name), list):
                raise SystemExit(f"schema 2.1 manifest.{name} 缺失或类型错误")
        entry_paths = {str(entry.get("relPath", "")) for entry in entries}
        external_ids: set[str] = set()
        for item in manifest["externalRoots"]:
            root_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(root_id, str) or not SAFE_ID.fullmatch(root_id) or root_id in external_ids:
                raise SystemExit(f"manifest external root id 非法或重复: {root_id!r}")
            external_ids.add(root_id)
            expected_prefix = ("codex/skills" if item.get("includedBy") == "codex"
                               else f"external-roots/{root_id}")
            if item.get("archivePrefix") != expected_prefix:
                raise SystemExit(f"manifest external root archivePrefix 非法: {root_id}")
            template = item.get("targetTemplate")
            explicit_required = item.get("requiresExplicitMapping")
            if type(explicit_required) is not bool:
                raise SystemExit(f"manifest external root mapping flag 非法: {root_id}")
            if explicit_required:
                if template is not None:
                    raise SystemExit(f"manifest external root 显式映射不得携带 template: {root_id}")
            elif not C.external_target_template_is_trusted(item):
                raise SystemExit(f"manifest external root targetTemplate 未在 allowlist: {root_id}")
        project_ids: set[str] = set()
        for item in manifest["projectMappings"]:
            project_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(project_id, str) or not SAFE_ID.fullmatch(project_id) or project_id in project_ids:
                raise SystemExit(f"manifest project id 非法或重复: {project_id!r}")
            project_ids.add(project_id)
            if item.get("archivePrefix") != f"projects/{project_id}/content":
                raise SystemExit(f"manifest project archivePrefix 非法: {project_id}")
            content_included = item.get("contentIncluded")
            if content_included is not None and type(content_included) is not bool:
                raise SystemExit(f"manifest project contentIncluded 类型非法: {project_id}")
            if content_included is False and any(
                    rel.startswith(f"projects/{project_id}/content/") for rel in entry_paths):
                raise SystemExit(f"manifest project 声明未含正文但 entries 存在: {project_id}")
        for item in manifest["links"]:
            if not isinstance(item, dict) or not _safe_posix_rel(item.get("relPath")):
                raise SystemExit("manifest link relPath 非法")
            root_id = item.get("externalRootId")
            if root_id is not None and root_id not in external_ids:
                raise SystemExit(f"manifest link 引用未知 external root: {root_id}")
            relative = item.get("targetRelativePath")
            if relative is not None and not _safe_posix_rel(relative, allow_empty=True):
                raise SystemExit(f"manifest link targetRelativePath 越界: {item.get('relPath')}")
        portable_auth = manifest.get("portableAuth", [])
        if not isinstance(portable_auth, list):
            raise SystemExit("schema 2.1 manifest.portableAuth 类型错误")
        for item in portable_auth:
            archive_path = item.get("archivePath") if isinstance(item, dict) else None
            if not _safe_posix_rel(archive_path) or archive_path not in entry_paths:
                raise SystemExit(f"manifest portableAuth archivePath 非法或缺失: {archive_path!r}")
        if schema == "2.2":
            local_projects = manifest.get("localMcpProjects")
            if not isinstance(local_projects, list):
                raise SystemExit("schema 2.2 manifest.localMcpProjects 缺失或类型错误")
            local_ids: set[str] = set()
            for item in local_projects:
                item_id = item.get("id") if isinstance(item, dict) else None
                if not isinstance(item_id, str) or not SAFE_ID.fullmatch(item_id) or item_id in local_ids:
                    raise SystemExit(f"manifest local MCP id 非法或重复: {item_id!r}")
                local_ids.add(item_id)
                required_item_keys = {
                    "id", "server", "profile", "archivePrefix", "target",
                    "argsTemplate", "argsPathRewrites", "envPathRewrites", "runtimeRecipe",
                    "reauthorizationRequired", "portableState", "excludedAccountState",
                    "installation",
                }
                optional_item_keys = {
                    "sourcePath", "commandKind", "commandName", "commandRelativePath",
                }
                if (not required_item_keys.issubset(item)
                        or not set(item).issubset(required_item_keys | optional_item_keys)):
                    raise SystemExit(f"manifest local MCP 字段非法: {item_id}")
                if item.get("archivePrefix") != f"local-mcp-projects/{item_id}/content":
                    raise SystemExit(f"manifest local MCP archivePrefix 非法: {item_id}")
                if any(
                    str(entry.get("relPath", "")).startswith(f"{item['archivePrefix']}/")
                    and entry.get("linkTarget") is not None
                    for entry in entries if isinstance(entry, dict)
                ):
                    raise SystemExit(f"manifest local MCP 不允许任何 symlink/junction entry: {item_id}")
                if (not _safe_single_segment(item.get("server"))
                        or not _safe_single_segment(item.get("profile"))):
                    raise SystemExit(f"manifest local MCP binding 非法: {item_id}")
                target = item.get("target")
                if not isinstance(target, dict) or target.get("kind") not in {"home", "localappdata", "explicit"}:
                    raise SystemExit(f"manifest local MCP target 类型非法: {item_id}")
                if type(target.get("requiresExplicitMapping")) is not bool:
                    raise SystemExit(f"manifest local MCP target mapping flag 非法: {item_id}")
                relative = target.get("relativePath")
                if target.get("kind") == "explicit":
                    if relative is not None or not target.get("requiresExplicitMapping"):
                        raise SystemExit(f"manifest local MCP explicit target 非法: {item_id}")
                elif not _safe_posix_rel(relative) or not C.local_auto_target_is_trusted(target):
                    raise SystemExit(f"manifest local MCP 自动 target 未在 allowlist: {item_id}")
                command_rel = item.get("commandRelativePath")
                if command_rel is not None and not _safe_posix_rel(command_rel):
                    raise SystemExit(f"manifest local MCP commandRelativePath 越界: {item_id}")
                args = item.get("argsTemplate")
                if (not isinstance(args, list) or not all(isinstance(value, str) for value in args)
                        or any(C.scan_secret_in_text(value) for value in args)):
                    raise SystemExit(f"manifest local MCP argsTemplate 非法: {item_id}")
                for rewrite in item.get("argsPathRewrites", []):
                    if (not isinstance(rewrite, dict) or not isinstance(rewrite.get("index"), int)
                            or rewrite["index"] < 0 or rewrite["index"] >= len(args)
                            or not _safe_posix_rel(rewrite.get("relativePath"))):
                        raise SystemExit(f"manifest local MCP argsPathRewrites 非法: {item_id}")
                for rewrite in item.get("envPathRewrites", []):
                    if (not isinstance(rewrite, dict)
                            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(rewrite.get("name", "")))
                            or not _safe_posix_rel(rewrite.get("relativePath"))):
                        raise SystemExit(f"manifest local MCP envPathRewrites 非法: {item_id}")
                recipe = item.get("runtimeRecipe")
                if not isinstance(recipe, dict) or recipe.get("type") not in {"python-uv-lock", "node-npm-lock"}:
                    raise SystemExit(f"manifest local MCP runtimeRecipe 未在 allowlist: {item_id}")
                if not _safe_posix_rel(recipe.get("lockFile")):
                    raise SystemExit(f"manifest local MCP lockFile 越界: {item_id}")
                if recipe.get("type") == "python-uv-lock":
                    if set(recipe) != {
                        "type", "python", "runtimeRelativePath", "lockFile",
                        "installLocalPackage", "verification",
                    }:
                        raise SystemExit(f"manifest local MCP Python recipe 字段非法: {item_id}")
                    if "nativeCredentialAddon" in recipe:
                        raise SystemExit(f"manifest local MCP Python recipe 不允许 native credential addon: {item_id}")
                    if (recipe.get("python") != "3.11"
                            or recipe.get("installLocalPackage") is not True
                            or recipe.get("runtimeRelativePath") != ".runtime"
                            or command_rel not in {
                                ".runtime/bin/python", ".runtime/Scripts/python.exe",
                            }):
                        raise SystemExit(f"manifest local MCP Python recipe 非法: {item_id}")
                    verification = recipe.get("verification") or {}
                    if set(verification) != {"type", "module"} or verification.get("type") != "python-import" or not re.fullmatch(
                            r"[A-Za-z_][A-Za-z0-9_.]*", str(verification.get("module", ""))):
                        raise SystemExit(f"manifest local MCP Python verification 非法: {item_id}")
                    if args != ["-m", verification["module"]] or item.get("argsPathRewrites") != []:
                        raise SystemExit(f"manifest local MCP Python args 未满足 typed contract: {item_id}")
                else:
                    if item.get("commandName") != "node" or command_rel is not None:
                        raise SystemExit(f"manifest local MCP Node launcher 非法: {item_id}")
                    allowed_recipe_keys = {"type", "lockFile", "installMode", "verification"}
                    if "nativeCredentialAddon" in recipe:
                        allowed_recipe_keys.add("nativeCredentialAddon")
                    if set(recipe) != allowed_recipe_keys:
                        raise SystemExit(f"manifest local MCP Node recipe 字段非法: {item_id}")
                    if recipe.get("installMode") != "npm-ci-ignore-scripts":
                        raise SystemExit(f"manifest local MCP Node recipe 非法: {item_id}")
                    verification = recipe.get("verification") or {}
                    if (set(verification) != {"type", "argIndex"}
                            or verification.get("type") != "node-check"
                            or type(verification.get("argIndex")) is not int
                            or verification["argIndex"] < 0
                            or verification["argIndex"] >= len(args)
                            or not any(rewrite.get("index") == verification["argIndex"]
                                       for rewrite in item.get("argsPathRewrites", []))):
                        raise SystemExit(f"manifest local MCP Node verification 非法: {item_id}")
                    rewrites = item.get("argsPathRewrites")
                    if (not args or not _looks_absolute_portable_path(args[0])
                            or type(rewrites) is not list or len(rewrites) != 1
                            or rewrites[0].get("index") != 0
                            or not str(rewrites[0].get("relativePath", "")).startswith("node_modules/")
                            or not C.node_item_has_trusted_launch_args(item)):
                        raise SystemExit(f"manifest local MCP Node args 未满足 typed contract: {item_id}")
                    if ("nativeCredentialAddon" in recipe
                            and not C.is_trusted_keytar_native_credential_addon(
                                recipe["nativeCredentialAddon"]
                            )):
                        raise SystemExit(f"manifest local MCP native credential addon 非法: {item_id}")
                portable_state = item.get("portableState")
                if (type(portable_state) is not list
                        or len(portable_state) != len(set(portable_state))
                        or any(type(rel) is not str
                               or rel not in C.LOCAL_MCP_PORTABLE_STATE
                               for rel in portable_state)):
                    raise SystemExit(f"manifest local MCP portableState 未在代码 allowlist: {item_id}")
                expected_state_entries = {
                    f"{item['archivePrefix']}/{rel}" for rel in portable_state
                }
                archived_state_entries = {
                    rel for rel in entry_paths
                    if rel.startswith(f"{item['archivePrefix']}/state/")
                }
                if expected_state_entries != archived_state_entries:
                    raise SystemExit(f"manifest local MCP portableState 与包内 entries 不一致: {item_id}")
                if not item.get("reauthorizationRequired"):
                    raise SystemExit(f"manifest local MCP 必须显式标记重新授权: {item_id}")
                _validate_installation(item, item_id)
        _validate_post_restore_actions(manifest)
        options = manifest.get("options") if isinstance(manifest.get("options"), dict) else {}
        enforce_blocking_gaps = bool(
            options.get("profile") == "complete"
            or (schema == "2.2" and manifest.get("localMcpProjects"))
            or any(str(entry.get("relPath", "")).startswith("local-mcp-projects/")
                   for entry in entries if isinstance(entry, dict))
        )
        if enforce_blocking_gaps:
            blocking = [
                gap for gap in manifest["coverageGaps"]
                if not isinstance(gap, dict)
                or gap.get("class") not in COMPLETE_NONBLOCKING_GAP_CLASSES
            ]
            if blocking:
                raise SystemExit("complete manifest 含阻断性 coverage gap，拒绝恢复")
        if options.get("profile") == "complete":
            providers = manifest.get("providerSources")
            if not isinstance(providers, list) or not providers:
                raise SystemExit("complete manifest 缺少 memory Provider 来源清单")
            for provider in providers:
                if not isinstance(provider, dict):
                    raise SystemExit("manifest providerSources 类型错误")
                if provider.get("included"):
                    if not any(str(entry.get("relPath", "")).startswith("hermes-provider/")
                               for entry in entries):
                        raise SystemExit("complete manifest 声称携带 Provider，但没有 Provider payload")
                elif (provider.get("gitDirty") or not provider.get("verifiedSource")
                      or not provider.get("sourceCommit")):
                    raise SystemExit("complete manifest 缺少可恢复的自定义/dirty memory Provider 来源")


def parse_maps(values: list[str] | None, option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for raw in values or []:
        if "=" not in raw:
            raise SystemExit(f"{option} 需要 ID=PATH: {raw}")
        key, value = raw.split("=", 1)
        if not key.strip() or not value.strip():
            raise SystemExit(f"{option} 需要非空 ID 与 PATH: {raw}")
        result[key.strip()] = Path(value.strip()).expanduser().resolve(strict=False)
    return result


def _target_platform(name: str | None = None) -> str:
    if name:
        return name
    if os.name == "nt":
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


def target_base(top: str, home: Path, hermes_target: Path,
                platform_name: str | None = None) -> Path | None:
    return {
        "codex": home / ".codex",
        "workbuddy": home / ".workbuddy",
        "hermes": hermes_target,
        "hermes-memory": home,
        "hermes-desktop": C.hermes_desktop_home_for_user(home, _target_platform(platform_name)),
        "hermes-provider": hermes_target / "plugins" / "memory",
    }.get(top)


def _root_target(item: dict, home: Path, explicit: dict[str, Path]) -> Path | None:
    if item.get("id") in explicit:
        return explicit[item["id"]]
    if not C.external_target_template_is_trusted(item):
        return None
    template = item.get("targetTemplate")
    if isinstance(template, str) and template.startswith("~/") and _safe_posix_rel(template[2:]):
        base = home.resolve(strict=False)
        candidate = (base / Path(*PurePosixPath(template[2:]).parts)).resolve(strict=False)
        try:
            candidate.relative_to(base)
        except ValueError:
            return None
        return candidate
    return None


def _local_mcp_target(item: dict, home: Path, explicit: dict[str, Path],
                      platform_name: str | None = None) -> Path | None:
    if item.get("id") in explicit:
        return explicit[item["id"]]
    target = item.get("target") or {}
    if not C.local_auto_target_is_trusted(target):
        return None
    relative = target.get("relativePath")
    if target.get("kind") == "home" and _safe_posix_rel(relative):
        base = home.resolve(strict=False)
    elif target.get("kind") == "localappdata" and _safe_posix_rel(relative):
        platform_name = _target_platform(platform_name)
        if platform_name == "windows":
            base = (home / "AppData" / "Local").resolve(strict=False)
        elif platform_name == "macos":
            base = (home / "Library" / "Application Support").resolve(strict=False)
        else:
            base = (home / ".local" / "share").resolve(strict=False)
    else:
        return None
    candidate = (base / Path(*PurePosixPath(relative).parts)).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def resolve_target(rel: str, home: Path, hermes_target: Path,
                   selected: set[str], manifest: dict | None = None,
                   project_maps: dict[str, Path] | None = None,
                   external_maps: dict[str, Path] | None = None,
                   local_mcp_maps: dict[str, Path] | None = None,
                   platform_name: str | None = None) -> tuple[Path, str] | None:
    parts = PurePosixPath(rel).parts
    top = parts[0]
    if top not in selected:
        return None
    manifest = manifest or {}
    project_maps = project_maps or {}
    external_maps = external_maps or {}
    local_mcp_maps = local_mcp_maps or {}
    rest = list(parts[1:])
    if top == "projects":
        if len(rest) < 2 or rest[1] != "content" or rest[0] not in project_maps:
            return None
        base = project_maps[rest[0]]
        rest = rest[2:]
    elif top == "external-roots":
        if not rest:
            return None
        root_id = rest[0]
        item = next((item for item in manifest.get("externalRoots", []) if item.get("id") == root_id), None)
        if item is None:
            return None
        base = _root_target(item, home, external_maps)
        rest = rest[1:]
    elif top == "local-mcp-projects":
        if len(rest) < 2 or rest[1] != "content":
            return None
        item_id = rest[0]
        item = next((item for item in manifest.get("localMcpProjects", []) if item.get("id") == item_id), None)
        if item is None:
            return None
        base = _local_mcp_target(item, home, local_mcp_maps, platform_name)
        rest = rest[2:]
    else:
        base = target_base(top, home, hermes_target, platform_name)
    if base is None:
        return None
    target = (base / Path(*rest)).resolve(strict=False)
    try:
        target.relative_to(base.resolve(strict=False))
    except ValueError:
        return None
    return target, top


def detect_fresh(home: Path, hermes_target: Path, manifest: dict | None = None,
                 local_mcp_maps: dict[str, Path] | None = None,
                 platform_name: str | None = None,
                 project_maps: dict[str, Path] | None = None,
                 external_maps: dict[str, Path] | None = None) -> dict:
    markers = {
        "codex": ["config.toml", "AGENTS.md", "skills", "memories", "automations"],
        "workbuddy": ["SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md", "settings.json", "skills"],
        "hermes": ["config.yaml", "SOUL.md", "skills", "memories", "state.db"],
        "hermes-memory": ["memory-tdai", "tdai-gateway.standalone.yaml"],
        "hermes-desktop": [],
        "hermes-provider": [],
    }
    result = {}
    for name, names in markers.items():
        base = target_base(name, home, hermes_target, platform_name)
        if name == "hermes-memory":
            base = home / ".memory-tencentdb"
        core = [item for item in names if (base / item).exists()]
        count = sum(1 for p in base.rglob("*") if p.is_file()) if base.is_dir() else 0
        result[name] = {"fresh": not core and count == 0, "coreFiles": core, "fileCount": count}
    occupied_local: list[dict[str, str]] = []
    for item in (manifest or {}).get("localMcpProjects", []):
        target = _local_mcp_target(
            item, home, local_mcp_maps or {}, platform_name
        )
        if target is not None and (target.exists() or target.is_symlink()):
            occupied_local.append({"id": str(item.get("id")), "target": str(target)})
    result["local-mcp-projects"] = {
        "fresh": not occupied_local,
        "occupiedTargets": occupied_local,
        "fileCount": sum(
            sum(1 for path in Path(item["target"]).rglob("*") if path.is_file())
            for item in occupied_local if Path(item["target"]).is_dir()
        ),
    }
    for part, items, resolver in (
        (
            "external-roots", (manifest or {}).get("externalRoots", []),
            lambda item: _root_target(item, home, external_maps or {}),
        ),
        (
            "projects", (manifest or {}).get("projectMappings", []),
            lambda item: (project_maps or {}).get(str(item.get("id"))),
        ),
    ):
        occupied: list[dict[str, str]] = []
        for item in items:
            target = resolver(item)
            if target is not None and (target.exists() or target.is_symlink()):
                occupied.append({"id": str(item.get("id")), "target": str(target)})
        result[part] = {
            "fresh": not occupied,
            "occupiedTargets": occupied,
            "fileCount": sum(
                sum(1 for path in Path(item["target"]).rglob("*") if path.is_file())
                for item in occupied if Path(item["target"]).is_dir()
            ),
        }
    return result


def mapped_link_target(entry: dict, target: Path, manifest: dict, home: Path,
                       external_maps: dict[str, Path]) -> Path | None:
    root_id = entry.get("externalRootId")
    if root_id:
        item = next((item for item in manifest.get("externalRoots", []) if item.get("id") == root_id), None)
        if item is None:
            return None
        base = _root_target(item, home, external_maps)
        if base is None:
            return None
        relative = entry.get("targetRelativePath") or ""
        if not _safe_posix_rel(relative, allow_empty=True):
            return None
        candidate = (base / Path(*PurePosixPath(relative).parts)).resolve(strict=False)
        try:
            candidate.relative_to(base.resolve(strict=False))
        except ValueError:
            return None
        return candidate
    raw = Path(str(entry.get("linkTarget", "")))
    if not raw.is_absolute():
        if ".." in raw.parts:
            return None
        return (target.parent / raw).resolve(strict=False)
    source_home = manifest.get("sourceUserHome")
    if source_home:
        try:
            relative = raw.resolve(strict=False).relative_to(Path(str(source_home)).resolve(strict=False))
            if not C.general_home_link_target_is_trusted(relative):
                return None
            return (home / relative).resolve(strict=False)
        except ValueError:
            pass
    return None


def build_plan(manifest: dict, home: Path, hermes_target: Path, selected: set[str],
               project_maps: dict[str, Path] | None = None,
               external_maps: dict[str, Path] | None = None,
               local_mcp_maps: dict[str, Path] | None = None,
               platform_name: str | None = None) -> dict:
    project_maps = project_maps or {}
    external_maps = external_maps or {}
    local_mcp_maps = local_mcp_maps or {}
    plan = {"overwrite": [], "create": [], "skip": [], "extra": [], "links": [],
            "identity": [], "unresolved": [], "linkDowngrades": []}
    wanted = {name: set() for name in VALID_PARTS}
    for entry in manifest["entries"]:
        rel = entry["relPath"]
        top = PurePosixPath(rel).parts[0]
        resolved = resolve_target(rel, home, hermes_target, selected, manifest,
                                  project_maps, external_maps, local_mcp_maps, platform_name)
        if resolved is None:
            if top in selected and top in {"projects", "external-roots", "local-mcp-projects"}:
                plan["unresolved"].append(rel)
            else:
                plan["skip"].append(rel)
            continue
        target, top = resolved
        if not entry.get("linkTarget"):
            wanted[top].add(rel.split("/", 1)[1])
        if entry.get("linkTarget"):
            destination = mapped_link_target(entry, target, manifest, home, external_maps)
            if destination is None:
                plan["unresolved"].append(f"{rel} -> {entry['linkTarget']}")
            else:
                plan["links"].append({"rel": rel, "target": target, "destination": destination,
                                      "linkType": entry.get("linkType", "symlink"),
                                      "isDirectory": bool(entry.get("linkIsDirectory"))})
        elif target.exists() and entry.get("sha256") and C.sha256_file(target) == entry["sha256"]:
            plan["skip"].append(rel)
        elif target.exists():
            plan["overwrite"].append((rel, target))
            if entry.get("type") in {"identity", "memory"}:
                plan["identity"].append(rel)
        else:
            plan["create"].append((rel, target))
    for top in selected & {"codex", "workbuddy", "hermes", "hermes-memory", "hermes-desktop", "hermes-provider"}:
        base = target_base(top, home, hermes_target, platform_name)
        wanted_here = wanted[top]
        extra_prefix = top + "/"
        if top == "hermes-memory":
            base = home / ".memory-tencentdb"
            wanted_here = {
                rel.split("/", 1)[1] for rel in wanted[top]
                if rel.startswith(".memory-tencentdb/")
            }
            extra_prefix = "hermes-memory/.memory-tencentdb/"
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() or path.is_symlink():
                    rel = path.relative_to(base).as_posix()
                    if rel not in wanted_here:
                        plan["extra"].append(extra_prefix + rel)
    return plan


def validate_target_portability(plan: dict, platform_name: str) -> None:
    """Fail before mutation on cross-filesystem name/case collisions."""
    targets: list[tuple[str, Path]] = [
        *(plan["overwrite"]), *(plan["create"]),
        *((item["rel"], item["target"]) for item in plan["links"]),
    ]
    seen: dict[str, str] = {}
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for rel, target in targets:
        text = unicodedata.normalize("NFC", str(target))
        key = text.casefold() if platform_name in {"windows", "macos"} else text
        previous = seen.get(key)
        if previous is not None and previous != rel:
            raise SystemExit(f"目标文件系统路径冲突: {previous} <-> {rel} -> {target}")
        seen[key] = rel
        if platform_name == "windows":
            for part in target.parts[1:]:
                if any(char in part for char in '<>:"|?*') or part.endswith((" ", ".")):
                    raise SystemExit(f"Windows 非法文件名: {rel} -> {part!r}")
                if part.split(".", 1)[0].upper() in reserved:
                    raise SystemExit(f"Windows 保留文件名: {rel} -> {part!r}")


def verify_archive_before_apply(reader: BackupReader, manifest: dict, selected: set[str],
                                home: Path, hermes_target: Path,
                                project_maps: dict[str, Path], external_maps: dict[str, Path],
                                local_mcp_maps: dict[str, Path],
                                platform_name: str) -> list[str]:
    """Verify every selected regular member before the first target mutation."""
    failures: list[str] = []
    for entry in manifest.get("entries", []):
        rel = entry["relPath"]
        if entry.get("linkTarget") is not None:
            continue
        resolved = resolve_target(rel, home, hermes_target, selected, manifest,
                                  project_maps, external_maps, local_mcp_maps, platform_name)
        if resolved is None:
            continue
        if not reader.exists(rel):
            failures.append(f"missing: {rel}")
            continue
        expected = entry.get("sha256")
        if expected:
            digest = hashlib.sha256()
            try:
                with reader.open(rel) as stream:
                    for chunk in iter(lambda: stream.read(1 << 20), b""):
                        digest.update(chunk)
            except (OSError, RuntimeError, NotImplementedError) as exc:
                failures.append(f"unreadable: {rel}: {exc}")
                continue
            if digest.hexdigest() != expected:
                failures.append(f"hash mismatch: {rel}")
    if "workbuddy" in selected and reader.exists("workbuddy/automations.json"):
        try:
            reader.read_json("workbuddy/automations.json")
        except Exception as exc:
            failures.append(f"invalid workbuddy/automations.json: {exc}")
    return failures


def archive_existing(target: Path, root: Path, rel: str) -> bool:
    if not (target.exists() or target.is_symlink()):
        return False
    archive = root / Path(*PurePosixPath(rel).parts)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() or archive.is_symlink():
        raise FileExistsError(f"冲突归档目标已存在: {archive}")
    shutil.move(str(target), str(archive))
    return True


def snapshot_in_place(target: Path, root: Path, rel: str,
                      changed: list[tuple[str, Path, bool]]) -> None:
    """Add an existing in-place repair to the same rollback transaction."""
    target_key = os.path.normcase(str(target.resolve(strict=False)))
    if any(os.path.normcase(str(path.resolve(strict=False))) == target_key
           for _rel, path, _had_old in changed):
        return
    if not target.is_file():
        raise FileNotFoundError(f"in-place repair target missing: {target}")
    archive = root / Path(*PurePosixPath(rel).parts)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() or archive.is_symlink():
        raise FileExistsError(f"冲突归档目标已存在: {archive}")
    shutil.copy2(target, archive)
    changed.append((rel, target, True))


def rollback_changes(changed: list[tuple[str, Path, bool]], conflict_root: Path) -> list[str]:
    """Best-effort rollback of files/links changed in the current apply."""
    failures: list[str] = []
    for rel, target, had_old in reversed(changed):
        try:
            if target.is_symlink() or C.is_junction(target) or target.is_file():
                if C.is_junction(target):
                    target.rmdir()
                else:
                    target.unlink(missing_ok=True)
            elif target.is_dir():
                shutil.rmtree(target)
            archived = conflict_root / Path(*PurePosixPath(rel).parts)
            if had_old and archived.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(archived), str(target))
        except OSError as exc:
            failures.append(f"rollback {rel}: {exc}")
    return failures


def old_homes(manifest: dict) -> list[str]:
    values = []
    source_user = manifest.get("sourceUserHome")
    if source_user:
        values.append(str(source_user))
    for name, source in (manifest.get("sources") or {}).items():
        if name not in {"codex", "workbuddy"}:
            continue
        raw = source.get("home") if isinstance(source, dict) else None
        if raw:
            path = Path(raw)
            home = str(path.parent) if path.name.lower() in {".codex", ".workbuddy"} else str(path)
            if home not in values:
                values.append(home)
    return values


def path_mappings(manifest: dict, home: Path, hermes_target: Path,
                  project_maps: dict[str, Path] | None = None,
                  external_maps: dict[str, Path] | None = None,
                  local_mcp_maps: dict[str, Path] | None = None,
                  platform_name: str | None = None) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = [(old, str(home)) for old in old_homes(manifest)]
    sources = manifest.get("sources") or {}
    hermes_source = sources.get("hermes", {}).get("home") if isinstance(sources.get("hermes"), dict) else None
    memory_source = sources.get("hermes-memory", {}).get("home") if isinstance(sources.get("hermes-memory"), dict) else None
    if hermes_source:
        mappings.append((str(hermes_source), str(hermes_target)))
    if memory_source:
        mappings.append((str(memory_source), str(home / ".memory-tencentdb")))
    desktop_source = sources.get("hermes-desktop", {}).get("home") if isinstance(sources.get("hermes-desktop"), dict) else None
    if desktop_source:
        mappings.append((str(desktop_source), str(C.hermes_desktop_home_for_user(home, _target_platform(platform_name)))))
    for item in manifest.get("projectMappings", []):
        if item.get("id") in (project_maps or {}):
            mappings.append((str(item.get("sourcePath")), str(project_maps[item["id"]])))
    for item in manifest.get("externalRoots", []):
        target = _root_target(item, home, external_maps or {})
        if target is not None:
            mappings.append((str(item.get("sourcePath")), str(target)))
    for item in manifest.get("localMcpProjects", []):
        target = _local_mcp_target(item, home, local_mcp_maps or {}, platform_name)
        if target is not None:
            mappings.append((str(item.get("sourcePath")), str(target)))
    unique = {}
    for old, new in mappings:
        unique[old] = new
    return sorted(unique.items(), key=lambda item: len(item[0]), reverse=True)


def remap_paths(path: Path, manifest: dict, home: Path, hermes_target: Path,
                project_maps: dict[str, Path] | None = None,
                external_maps: dict[str, Path] | None = None,
                local_mcp_maps: dict[str, Path] | None = None,
                platform_name: str | None = None) -> bool:
    if path.name not in PATH_CONFIG_NAMES:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    original = text
    for old, new in path_mappings(manifest, home, hermes_target, project_maps,
                                  external_maps, local_mcp_maps, platform_name):
        for before, after in (
            (old.replace("\\", "\\\\"), new.replace("\\", "\\\\")),
            (old.replace("\\", "/"), new.replace("\\", "/")),
            (old, new),
        ):
            text = re.sub(re.escape(before), lambda _: after, text, flags=re.IGNORECASE)
    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _set_env_values(path: Path, values: dict[str, str], remove_keys: set[str] | None = None,
                    before_write=None) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    lines = text.splitlines()
    remaining = dict(values)
    remove_keys = remove_keys or set()
    for index, line in enumerate(lines):
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if not match:
            continue
        key = match.group(1)
        if key in remove_keys:
            lines[index] = (
                f"# {key} removed by Ark 3.2; install the target-platform runtime "
                "and use Hermes auto-discovery"
            )
        elif key in remaining:
            lines[index] = f"{key}={remaining.pop(key)}"
    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Ark 3.2 portable Hermes memory paths")
        lines.extend(f"{key}={value}" for key, value in remaining.items())
    text = "\n".join(lines) + ("\n" if original.endswith(("\n", "\r")) else "")
    if text == original:
        return False
    if before_write is not None:
        before_write()
    path.write_text(text, encoding="utf-8")
    return True


def _set_gateway_data_dir(path: Path, data_dir: Path, before_write=None) -> bool:
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    original = list(lines)
    data_index = None
    replaced = False
    for index, line in enumerate(lines):
        if re.match(r"^data:\s*(?:#.*)?$", line):
            data_index = index
            continue
        if data_index is not None and re.match(r"^\S", line):
            break
        if data_index is not None and re.match(r"^\s+baseDir\s*:", line):
            indent = re.match(r"^(\s*)", line).group(1)
            lines[index] = f'{indent}baseDir: "{data_dir.as_posix()}"'
            replaced = True
            break
    if data_index is not None and not replaced:
        lines.insert(data_index + 1, f'  baseDir: "{data_dir.as_posix()}"')
    if lines == original:
        return False
    if before_write is not None:
        before_write()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def repair_hermes_memory_paths(
        home: Path, hermes_target: Path, conflict_root: Path | None = None,
        transaction_changes: list[tuple[str, Path, bool]] | None = None,
) -> tuple[list[str], list[str]]:
    """把来源机绝对路径固定到目标用户目录下的可迁移布局。"""
    changed: list[str] = []
    warnings: list[str] = []
    memory_root = (home / ".memory-tencentdb").resolve(strict=False)
    data_dir = memory_root / "memory-tdai"
    gateway_config = memory_root / "tdai-gateway.standalone.yaml"
    env_path = hermes_target / ".env"
    env_values = {
        "TDAI_GATEWAY_CONFIG": f'"{gateway_config.as_posix()}"',
        "TDAI_DATA_DIR": f'"{data_dir.as_posix()}"',
        "MEMORY_TENCENTDB_ROOT": f'"{memory_root.as_posix()}"',
    }
    def track(path: Path, rel: str) -> None:
        if conflict_root is not None and transaction_changes is not None:
            snapshot_in_place(path, conflict_root, rel, transaction_changes)

    if _set_env_values(
            env_path, env_values, {"MEMORY_TENCENTDB_GATEWAY_CMD"},
            lambda: track(env_path, "hermes/.env")):
        changed.append("hermes/.env (TencentDB data/config paths; runtime uses auto-discovery)")
    elif not env_path.is_file():
        warnings.append("Hermes .env 未恢复；腾讯记忆密钥与网关路径不可自动启用")
    if _set_gateway_data_dir(
            gateway_config, data_dir,
            lambda: track(
                gateway_config,
                "hermes-memory/.memory-tencentdb/tdai-gateway.standalone.yaml",
            )):
        changed.append("hermes-memory/.memory-tencentdb/tdai-gateway.standalone.yaml")
    elif not gateway_config.is_file():
        warnings.append("tdai-gateway.standalone.yaml 未恢复")
    return changed, warnings


def merge_portable_environment(hermes_target: Path) -> bool:
    source = hermes_target / ".ark-portable-environment.env"
    target = hermes_target / ".env"
    if not source.is_file() or not target.is_file():
        return False
    values: dict[str, str] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return bool(values) and _set_env_values(target, values)


def remap_projects_databases(
        manifest: dict, hermes_target: Path, project_maps: dict[str, Path],
        conflict_root: Path | None = None,
        transaction_changes: list[tuple[str, Path, bool]] | None = None,
) -> list[str]:
    """Rewrite projects.db registry paths after restoring mapped project content."""
    by_profile: dict[str, list[tuple[str, str]]] = {}
    for mapping in manifest.get("projectMappings", []):
        target = project_maps.get(mapping.get("id"))
        if target is None:
            continue
        for origin in mapping.get("origins", []):
            if origin.get("kind") == "projects.db" and origin.get("projectId"):
                by_profile.setdefault(origin.get("profile", "default"), []).append(
                    (str(origin["projectId"]), str(target))
                )
    changed: list[str] = []
    for profile, rows in by_profile.items():
        root = hermes_target if profile == "default" else hermes_target / "profiles" / profile
        db = root / "projects.db"
        if not db.is_file():
            continue
        rel = ("hermes/projects.db" if profile == "default"
               else f"hermes/profiles/{profile}/projects.db")
        try:
            con = sqlite3.connect(db)
            try:
                columns = {row[1] for row in con.execute("PRAGMA table_info(projects)")}
                needs_change = False
                for project_id, target in rows:
                    current = con.execute(
                        "SELECT path FROM project_folders WHERE project_id=?", (project_id,)
                    ).fetchone()
                    needs_change = needs_change or (current is not None and current[0] != target)
                    if "primary_path" in columns:
                        current_primary = con.execute(
                            "SELECT primary_path FROM projects WHERE id=?", (project_id,)
                        ).fetchone()
                        needs_change = needs_change or (
                            current_primary is not None and current_primary[0] != target
                        )
            finally:
                con.close()
            if not needs_change:
                continue
            if conflict_root is not None and transaction_changes is not None:
                snapshot_in_place(db, conflict_root, rel, transaction_changes)
            con = sqlite3.connect(db)
            try:
                columns = {row[1] for row in con.execute("PRAGMA table_info(projects)")}
                for project_id, target in rows:
                    con.execute(
                        "UPDATE project_folders SET path=? WHERE project_id=?", (target, project_id)
                    )
                    if "primary_path" in columns:
                        con.execute(
                            "UPDATE projects SET primary_path=? WHERE id=?", (target, project_id)
                        )
                con.commit()
            finally:
                con.close()
            changed.append(rel + " (project mappings)")
        except sqlite3.Error as exc:
            raise RuntimeError(f"projects.db mapping failed for {profile}: {exc}") from exc
    return changed


def preflight_local_mcp_runtime(manifest: dict, selected: set[str], platform_name: str) -> None:
    """Validate fixed executors before any restore target is mutated."""
    if "local-mcp-projects" not in selected or not manifest.get("localMcpProjects"):
        return
    if platform_name != _target_platform():
        raise SystemExit(
            "local MCP 运行时只能在目标操作系统本机重建；--target-platform 与当前系统不同，未写入目标。"
        )
    try:
        import yaml  # noqa: F401  # type: ignore
    except ImportError as exc:
        raise SystemExit("local MCP 配置改写需要 PyYAML；未写入目标。请先安装目标版 Hermes/PyYAML。") from exc
    recipe_types = {item.get("runtimeRecipe", {}).get("type") for item in manifest["localMcpProjects"]}
    if "python-uv-lock" in recipe_types and shutil.which("uv") is None:
        raise SystemExit("local MCP Python 重建需要 allowlisted executor uv；未写入目标。")
    if "node-npm-lock" in recipe_types:
        if shutil.which("npm") is None or shutil.which("node") is None:
            raise SystemExit("local MCP Node 重建需要 npm 与 node；未写入目标。")


def _run_recipe(argv: list[str], cwd: Path, label: str) -> str:
    """Execute one code-owned argv vector; manifest never supplies commands."""
    try:
        result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                                timeout=900, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"{label}: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip().replace("\r", " ").replace("\n", " ")
        raise RuntimeError(f"{label} failed ({result.returncode}): {detail[:500]}")
    return (result.stdout or result.stderr or "").strip()


def _python_runtime_path(root: Path, platform_name: str) -> Path:
    return root / ".runtime" / ("Scripts/python.exe" if platform_name == "windows" else "bin/python")


def rebuild_local_mcp_runtimes(manifest: dict, home: Path, selected: set[str],
                               local_mcp_maps: dict[str, Path], platform_name: str,
                               conflict_root: Path,
                               changed: list[tuple[str, Path, bool]]) -> list[dict]:
    results: list[dict] = []
    if "local-mcp-projects" not in selected:
        return results
    for item in manifest.get("localMcpProjects", []):
        root = _local_mcp_target(item, home, local_mcp_maps, platform_name)
        if root is None:
            raise RuntimeError(f"local MCP target unresolved after plan: {item.get('id')}")
        recipe = item["runtimeRecipe"]
        lock = root / Path(*PurePosixPath(recipe["lockFile"]).parts)
        if not lock.is_file():
            raise RuntimeError(f"local MCP lock missing after copy: {item.get('id')}/{recipe['lockFile']}")
        if recipe["type"] == "python-uv-lock":
            try:
                lock_bytes = lock.read_bytes()
            except OSError as exc:
                raise RuntimeError(f"local MCP Python lock unreadable: {item.get('id')}: {exc}") from exc
            if C.parse_hash_locked_requirements(lock_bytes) is None:
                raise RuntimeError(f"local MCP Python lock contains unsafe or unverified directives: {item.get('id')}")
            runtime = root / Path(*PurePosixPath(recipe["runtimeRelativePath"]).parts)
            runtime_rel = f"local-mcp-projects/{item['id']}/runtime"
            had_old = archive_existing(runtime, conflict_root, runtime_rel)
            changed.append((runtime_rel, runtime, had_old))
            _run_recipe([shutil.which("uv"), "venv", "--python", "3.11", str(runtime)], root,
                        f"{item['id']} uv venv")
            python = _python_runtime_path(root, platform_name)
            _run_recipe([shutil.which("uv"), "pip", "sync", "--python", str(python),
                         "--require-hashes", str(lock)], root, f"{item['id']} locked dependency sync")
            _run_recipe([shutil.which("uv"), "pip", "install", "--python", str(python),
                         "--no-deps", str(root)], root, f"{item['id']} local package install")
            module = recipe["verification"]["module"]
            _run_recipe([str(python), "-I", "-c",
                         "import importlib,sys; importlib.import_module(sys.argv[1])", module],
                        root, f"{item['id']} import verification")
            results.append({
                "id": item["id"], "server": item["server"], "profile": item["profile"],
                "recipe": recipe["type"], "codeHealth": "passed-python-import",
                "reauthorization": "required",
            })
        elif recipe["type"] == "node-npm-lock":
            try:
                lock_bytes = lock.read_bytes()
                derived_installation = C.build_local_mcp_installation(item, lock_bytes)
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"local MCP npm lock contains unsafe or unverified resolution: {item.get('id')}: {exc}") from exc
            if derived_installation != item.get("installation"):
                raise RuntimeError(f"local MCP npm installation evidence drifted before execution: {item.get('id')}")
            derived_addon, addon_gap = C.derive_keytar_native_credential_addon(lock_bytes)
            if addon_gap is not None or recipe.get("nativeCredentialAddon") != derived_addon:
                raise RuntimeError(f"local MCP keytar trust could not be re-derived before execution: {item.get('id')}")
            runtime = root / "node_modules"
            runtime_rel = f"local-mcp-projects/{item['id']}/node_modules"
            had_old = archive_existing(runtime, conflict_root, runtime_rel)
            changed.append((runtime_rel, runtime, had_old))
            _run_recipe([shutil.which("npm"), "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                        root, f"{item['id']} npm ci")
            credential_addon = recipe.get("nativeCredentialAddon")
            if credential_addon is not None:
                # npm ci must not be able to change the lock that authorizes the
                # sole foreground lifecycle-script exception.
                current_lock = lock.read_bytes()
                current_addon, current_gap = C.derive_keytar_native_credential_addon(current_lock)
                if (current_lock != lock_bytes or current_gap is not None
                        or current_addon != C.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON):
                    raise RuntimeError(
                        f"local MCP keytar trust changed before native rebuild: {item.get('id')}"
                    )
                _run_recipe([shutil.which("npm"), "rebuild", "keytar", "--foreground-scripts",
                             "--no-audit", "--no-fund"],
                            root, f"{item['id']} audited keytar rebuild")
                _run_recipe([shutil.which("node"), "-e", "require('keytar')"],
                            root, f"{item['id']} keytar binding verification")
            entry = Path(_typed_local_mcp_args(item, root)[0])
            _run_recipe([shutil.which("node"), "--check", str(entry)], root,
                        f"{item['id']} node discovery")
            results.append({
                "id": item["id"], "server": item["server"], "profile": item["profile"],
                "recipe": recipe["type"],
                "codeHealth": ("passed-node-check+credential-addon-verified"
                               if credential_addon is not None else "passed-node-check"),
                "reauthorization": "required",
            })
        else:  # validate_manifest should make this unreachable.
            raise RuntimeError(f"local MCP recipe not allowlisted: {recipe.get('type')}")
    return results


def rewrite_local_mcp_configs(manifest: dict, home: Path, hermes_target: Path,
                              selected: set[str], local_mcp_maps: dict[str, Path],
                              platform_name: str, conflict_root: Path,
                              changed: list[tuple[str, Path, bool]]) -> list[str]:
    """Update only typed command/arg/env path fields in restored Hermes YAML."""
    if "local-mcp-projects" not in selected or "hermes" not in selected:
        return []
    import yaml  # type: ignore
    rewritten: list[str] = []
    by_config: dict[Path, list[dict]] = {}
    for item in manifest.get("localMcpProjects", []):
        config = (hermes_target / "config.yaml" if item.get("profile") == "default"
                  else hermes_target / "profiles" / str(item.get("profile")) / "config.yaml")
        by_config.setdefault(config, []).append(item)
    for config, items in by_config.items():
        if not config.is_file():
            raise RuntimeError(f"restored Hermes config missing for local MCP bindings: {config}")
        original = config.read_text(encoding="utf-8")
        data = yaml.safe_load(original) or {}
        servers = data.get("mcp_servers") if isinstance(data, dict) else None
        if not isinstance(servers, dict):
            raise RuntimeError(f"mcp_servers missing in restored Hermes config: {config}")
        mutated = False
        for item in items:
            spec = servers.get(item["server"])
            if not isinstance(spec, dict):
                raise RuntimeError(f"local MCP server missing in restored config: {item['profile']}/{item['server']}")
            root = _local_mcp_target(item, home, local_mcp_maps, platform_name)
            if root is None:
                raise RuntimeError(f"local MCP target unresolved: {item['id']}")
            recipe = item["runtimeRecipe"]
            if recipe["type"] == "python-uv-lock":
                spec["command"] = str(_python_runtime_path(root, platform_name))
            else:
                spec["command"] = "node"
            spec["args"] = _typed_local_mcp_args(item, root)
            env = spec.get("env") if isinstance(spec.get("env"), dict) else {}
            for rewrite in item.get("envPathRewrites", []):
                env[rewrite["name"]] = str(root / Path(*PurePosixPath(rewrite["relativePath"]).parts))
            if env:
                spec["env"] = env
            mutated = True
        if mutated:
            rendered = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
            if rendered == original:
                continue
            profile = str(items[0].get("profile") or "default")
            config_rel = ("hermes/config.yaml" if profile == "default"
                          else f"hermes/profiles/{profile}/config.yaml")
            config_key = os.path.normcase(str(config.resolve(strict=False)))
            already_tracked = any(
                os.path.normcase(str(target.resolve(strict=False))) == config_key
                for _rel, target, _had_old in changed
            )
            if not already_tracked:
                had_old = archive_existing(config, conflict_root, config_rel)
                changed.append((config_rel, config, had_old))
            config.write_text(rendered, encoding="utf-8")
            rewritten.append(str(config))
    return rewritten


def create_portable_link(item: dict, conflict_root: Path, errors: list[str],
                         downgrades: list[dict]) -> tuple[bool, bool]:
    target: Path = item["target"]
    destination: Path = item["destination"]
    rel = item["rel"]
    had_old = False
    mutated = False
    try:
        had_old = archive_existing(target, conflict_root, rel)
    except OSError as exc:
        errors.append(f"link {rel}: conflict archive failed: {exc}")
        return False, False
    mutated = had_old
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt" and item.get("linkType") == "junction" and item.get("isDirectory"):
            script = "& { param($linkPath,$targetPath) New-Item -ItemType Junction -Path $linkPath -Target $targetPath | Out-Null }"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script,
                                     str(target), str(destination)], capture_output=True,
                                    text=True, timeout=20)
            if result.returncode:
                raise OSError((result.stderr or result.stdout).strip())
        else:
            target.symlink_to(destination, target_is_directory=bool(item.get("isDirectory")))
        mutated = True
        return had_old, mutated
    except (OSError, subprocess.SubprocessError) as exc:
        # Never materialize the target tree silently. A marker keeps the missing
        # topology explicit and gives an AI enough information to finish later.
        try:
            if item.get("isDirectory"):
                target.mkdir(parents=True, exist_ok=False)
                marker = target / ".ark-link-degraded.json"
            else:
                marker = target.with_name(target.name + ".ark-link-degraded.json")
            marker.write_text(json.dumps({
                "schema": "ark-link-degraded-v1", "relPath": rel,
                "requestedType": item.get("linkType"), "target": str(destination),
                "reason": str(exc),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            mutated = True
            downgrades.append({"relPath": rel, "marker": str(marker), "target": str(destination)})
        except OSError as marker_exc:
            errors.append(f"link {rel}: {exc}; downgrade marker failed: {marker_exc}")
        return had_old, mutated


def automation_plan(reader: BackupReader, report_root: Path, manifest: dict, home: Path) -> Path | None:
    rel = "workbuddy/automations.json"
    if not reader.exists(rel):
        return None
    data = reader.read_json(rel)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for old in old_homes(manifest):
        text = re.sub(re.escape(old), lambda _: str(home), text, flags=re.IGNORECASE)
        text = re.sub(re.escape(old.replace("\\", "/")), lambda _: str(home).replace("\\", "/"), text,
                      flags=re.IGNORECASE)
    data = json.loads(text)
    data["restoreStatus"] = "pending-official-api"
    data["restoreInstruction"] = "由 AI 使用 WorkBuddy 官方自动化接口逐项创建并回读；禁止直写 workbuddy.db。"
    out = report_root / "workbuddy-automations-restore-plan.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def render_report(manifest: dict, plan: dict, backup: str, conflict_root: Path, errors: list[str],
                  failed: list[str], remapped: list[str], auto_plan: Path | None) -> str:
    lines = [
        "# 方舟恢复报告", "",
        f"- 备份：`{backup}`",
        f"- 备份时间：{manifest.get('createdAt', '未知')}（schema {manifest.get('schemaVersion', '未知')}）",
        f"- 执行时间：{C.utc_now()}",
        f"- 覆盖：{len(plan['overwrite'])}；新增：{len(plan['create'])}；已一致：{len(plan['skip'])}",
        f"- 本地多出：{len(plan['extra'])}（仅报告，未删除）",
        f"- 冲突旧文件归档：`{conflict_root}`",
        f"- 路径自动适配：{len(remapped)} 个配置文件", "",
    ]
    if auto_plan:
        lines += [f"- WorkBuddy 自动化恢复计划：`{auto_plan}`（尚未写入，需官方接口执行并回读）", ""]
    if remapped:
        lines += ["## 已适配路径", *[f"- {item}" for item in remapped], ""]
    if errors:
        lines += ["## 错误", *[f"- {item}" for item in errors], ""]
    if failed:
        lines += ["## 源内容校验失败", *[f"- {item}" for item in failed], ""]
    if plan.get("linkDowngrades"):
        lines += ["## Link 降级（未实体化源目录）"]
        for item in plan["linkDowngrades"]:
            lines.append(f"- `{item['relPath']}` → `{item['target']}`；标记 `{item['marker']}`")
        lines.append("")
    if plan.get("localMcpRuntime"):
        lines += ["## Local stdio MCP code health", ""]
        for item in plan["localMcpRuntime"]:
            lines.append(
                f"- `{item.get('profile')}/{item.get('server')}`：{item.get('codeHealth')} "
                f"({item.get('recipe')})；账号状态：{item.get('reauthorization')}"
            )
        lines += ["", "代码导入/入口检查通过不代表 Apple Music 或其他账号已授权；重新授权是独立必做项。", ""]
    if manifest.get("postRestoreActions"):
        lines += ["## 恢复后动作"]
        for item in manifest["postRestoreActions"]:
            lines.append(f"- [{'必须' if item.get('required') else '建议'}] {item.get('action')}")
        lines.append("")
    lines += ["## 结论", "", "源文件写入后已先按 manifest 校验；路径适配会使最终 hash 变化，这是预期结果。",
              "账号登录文件、Cookie、系统钥匙串和 OAuth 授权不在恢复范围内；请按新设备流程重新登录。"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="方舟恢复：默认只读预览，显式 --apply 才写入")
    parser.add_argument("backup", help="备份目录或 .zip")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只输出计划，不写目标/备份目录（默认）")
    mode.add_argument("--apply", action="store_true", help="执行恢复；覆盖前始终归档旧文件")
    parser.add_argument(
        "--parts", default="codex,workbuddy,hermes,hermes-memory,hermes-desktop,hermes-provider,external-roots,local-mcp-projects",
        help="默认恢复全部可安全自动映射的用户态；projects 需 --project-map",
    )
    parser.add_argument("--target-home", help="目标用户主目录；默认当前用户")
    parser.add_argument("--target-hermes-home", help="Hermes 目标数据目录；默认按目标操作系统自动解析 HERMES_HOME")
    parser.add_argument("--target-platform", choices=["windows", "macos", "linux"],
                        help="生成跨系统路径；默认当前运行系统")
    parser.add_argument("--project-map", action="append", metavar="ID=PATH",
                        help="项目恢复目标，可重复；ID 来自 manifest.projectMappings")
    parser.add_argument("--external-root-map", action="append", metavar="ID=PATH",
                        help="没有 ~/ targetTemplate 的 external root 显式目标，可重复")
    parser.add_argument("--local-mcp-map", action="append", metavar="ID=PATH",
                        help="没有安全自动目标的 local stdio MCP 项目映射，可重复")
    parser.add_argument("--replace-portable-auth", action="store_true",
                        help="允许凭据舱覆盖目标已有 OAuth JSON；默认保留目标现有凭据")
    parser.add_argument("--fresh", action="store_true", help="断言目标为空；检测到现有环境则停止")
    parser.add_argument("--no-remap-paths", action="store_true", help="不适配旧用户主目录")
    parser.add_argument("--apply-automations", action="store_true", help="已停用：改用官方自动化接口")
    parser.add_argument("--zip-password", help="兼容旧版；不推荐直接传口令")
    parser.add_argument("--password-file", help="从文件读取口令")
    parser.add_argument("--password-env", help="从指定环境变量读取口令")
    parser.add_argument("--prompt-password", action="store_true", help="隐藏输入口令")
    parser.add_argument("--quiet", action="store_true")
    opts = parser.parse_args()

    if opts.apply_automations:
        raise SystemExit("--apply-automations 已停用：不会直写 workbuddy.db；请使用官方自动化接口。")
    selected = {item.strip() for item in opts.parts.split(",") if item.strip()}
    unknown = selected - VALID_PARTS
    if unknown:
        raise SystemExit(f"未知恢复范围: {sorted(unknown)}")
    project_maps = parse_maps(opts.project_map, "--project-map")
    external_maps = parse_maps(opts.external_root_map, "--external-root-map")
    local_mcp_maps = parse_maps(opts.local_mcp_map, "--local-mcp-map")
    if project_maps and "projects" not in selected:
        C.warn("提供了 --project-map 但 --parts 未选择 projects；映射不会写入。", opts.quiet)
    home = Path(opts.target_home).expanduser().resolve() if opts.target_home else Path.home().resolve()
    target_platform = _target_platform(opts.target_platform)
    if opts.target_hermes_home:
        hermes_target = Path(opts.target_hermes_home).expanduser().resolve()
    elif opts.target_home:
        hermes_target = ((home / "AppData" / "Local" / "hermes")
                          if target_platform == "windows" else (home / ".hermes")).resolve()
    else:
        hermes_target = C.hermes_home().expanduser().resolve()
    reader = BackupReader(opts.backup, resolve_password(opts))
    try:
        manifest = reader.read_json("manifest.json")
        validate_manifest(manifest)
        validate_installation_evidence(reader, manifest)
        fresh = detect_fresh(
            home, hermes_target, manifest, local_mcp_maps, target_platform,
            project_maps, external_maps,
        )
        if opts.fresh:
            occupied: list[str] = []
            for part in sorted(selected):
                state = fresh.get(part)
                if not state or state.get("fresh"):
                    continue
                targets = state.get("occupiedTargets") or []
                if targets:
                    occupied.extend(
                        f"{part}:{item['id']}={item['target']}" for item in targets
                    )
                else:
                    occupied.append(part)
            if occupied:
                raise SystemExit(f"--fresh 断言失败，目标已有内容: {occupied}；未写入。")
        plan = build_plan(manifest, home, hermes_target, selected, project_maps,
                          external_maps, local_mcp_maps, target_platform)
        if not opts.replace_portable_auth:
            auth_paths = {item.get("archivePath") for item in manifest.get("portableAuth", [])
                          if isinstance(item, dict)}
            preserved = [(rel, target) for rel, target in plan["overwrite"] if rel in auth_paths]
            if preserved:
                plan["overwrite"] = [(rel, target) for rel, target in plan["overwrite"]
                                     if rel not in auth_paths]
                plan["skip"].extend(rel for rel, _target in preserved)
                C.warn(f"保留目标已有 OAuth 凭据 {len(preserved)} 项；需要覆盖时使用 --replace-portable-auth。",
                       opts.quiet)
        validate_target_portability(plan, target_platform)
        C.info(f"计划：覆盖 {len(plan['overwrite'])}，新增 {len(plan['create'])}，已一致 {len(plan['skip'])}，未映射 {len(plan['unresolved'])}，本地多出 {len(plan['extra'])}", opts.quiet)
        if plan["identity"]:
            C.warn("将覆盖身份/记忆文件；执行时旧版会先归档：" + "、".join(plan["identity"][:12]), opts.quiet)
        if not opts.apply:
            for rel, target in sorted(plan["overwrite"])[:50]:
                C.info(f"  [覆盖] {rel} -> {target}", opts.quiet)
            for rel, target in sorted(plan["create"])[:50]:
                C.info(f"  [新增] {rel} -> {target}", opts.quiet)
            for rel in sorted(plan["unresolved"])[:50]:
                C.warn(f"  [待映射] {rel}", opts.quiet)
            for item in manifest.get("localMcpProjects", []):
                if "local-mcp-projects" in selected:
                    C.info(
                        f"  [运行时配方] {item.get('profile')}/{item.get('server')} -> "
                        f"{item.get('runtimeRecipe', {}).get('type')}；重新授权 required",
                        opts.quiet,
                    )
            C.info("只读预览完成：目标目录与备份包均未写入。确认后单独使用 --apply。", opts.quiet)
            return 0

        if plan["unresolved"]:
            raise SystemExit(
                "存在未映射的 project/external root/local MCP/link，apply 已停止；请按 CONFIGURATION.md 提供映射：\n- "
                + "\n- ".join(plan["unresolved"][:50])
            )
        if "hermes-desktop" in selected:
            desktop_target = C.hermes_desktop_home_for_user(home, target_platform)
            lock = C.directory_lock_status(desktop_target / "Local Storage" / "leveldb" / "LOCK")
            if lock.get("exclusiveRead") is False:
                raise SystemExit("目标 Hermes Desktop Local Storage 正在使用；请退出 Desktop 后重试，未写入。")
        preflight_local_mcp_runtime(manifest, selected, target_platform)
        archive_failures = verify_archive_before_apply(
            reader, manifest, selected, home, hermes_target,
            project_maps, external_maps, local_mcp_maps, target_platform,
        )
        if archive_failures:
            raise SystemExit("备份完整性预检失败，目标未写入：\n- " + "\n- ".join(archive_failures[:50]))

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        conflict_root = home / ".ark" / "restore-conflicts" / stamp
        report_root = home / ".ark" / "restore-reports" / stamp
        conflict_root.mkdir(parents=True, exist_ok=False)
        report_root.mkdir(parents=True, exist_ok=False)
        errors: list[str] = []
        failed: list[str] = []
        remapped: list[str] = []
        changed: list[tuple[str, Path, bool]] = []
        entry_map = {entry["relPath"]: entry for entry in manifest["entries"]}
        for rel, target in plan["overwrite"] + plan["create"]:
            try:
                if not reader.exists(rel):
                    errors.append(f"备份内缺失: {rel}")
                    continue
                had_old = archive_existing(target, conflict_root, rel)
                changed.append((rel, target, had_old))
                reader.copy_to(rel, target)
                expected = entry_map[rel].get("sha256")
                if expected and C.sha256_file(target) != expected:
                    failed.append(rel)
            except OSError as exc:
                errors.append(f"{rel}: {exc}")
        for item in plan["links"]:
            target = item["target"]
            had_old, mutated = create_portable_link(
                item, conflict_root, errors, plan["linkDowngrades"]
            )
            if had_old or mutated:
                changed.append((item["rel"], target, had_old))
        if errors or failed:
            rollback_errors = rollback_changes(changed, conflict_root)
            errors.extend(rollback_errors)
            errors.append("本次写入已执行回滚" if not rollback_errors else "本次写入回滚不完整")
            auto_plan = None
            report = render_report(manifest, plan, str(reader.path), conflict_root,
                                   errors, failed, remapped, auto_plan)
            report_path = report_root / "restore-report.md"
            report_path.write_text(report, encoding="utf-8")
            C.warn(f"恢复失败并回滚；报告 {report_path}", opts.quiet)
            return 1
        try:
            if not opts.no_remap_paths:
                for rel, target in plan["overwrite"] + plan["create"]:
                    if target.is_file() and remap_paths(target, manifest, home, hermes_target,
                                                        project_maps, external_maps, local_mcp_maps,
                                                        target_platform):
                        remapped.append(rel)
                if "hermes-memory" in selected and "hermes/.env" in entry_map:
                    memory_remapped, memory_warnings = repair_hermes_memory_paths(
                        home, hermes_target, conflict_root, changed
                    )
                    remapped.extend(memory_remapped)
                    for warning in memory_warnings:
                        C.warn(warning, opts.quiet)
                # Legacy `.ark-portable-environment.env` is never auto-merged:
                # ambient values can belong to another profile/service account.
                remapped.extend(remap_projects_databases(
                    manifest, hermes_target, project_maps, conflict_root, changed
                ))
            plan["localMcpRuntime"] = rebuild_local_mcp_runtimes(
                manifest, home, selected, local_mcp_maps, target_platform,
                conflict_root, changed,
            )
            remapped.extend(rewrite_local_mcp_configs(
                manifest, home, hermes_target, selected, local_mcp_maps, target_platform,
                conflict_root, changed,
            ))
            auto_plan = automation_plan(reader, report_root, manifest, home)
        except Exception as exc:
            errors.append(f"post-copy transformation failed: {exc}")
            rollback_errors = rollback_changes(changed, conflict_root)
            errors.extend(rollback_errors)
            errors.append("本次写入已执行回滚" if not rollback_errors else "本次写入回滚不完整")
            report = render_report(manifest, plan, str(reader.path), conflict_root,
                                   errors, failed, remapped, None)
            report_path = report_root / "restore-report.md"
            report_path.write_text(report, encoding="utf-8")
            C.warn(f"恢复后处理失败并回滚；报告 {report_path}", opts.quiet)
            return 1
        report = render_report(manifest, plan, str(reader.path), conflict_root, errors, failed, remapped, auto_plan)
        report_path = report_root / "restore-report.md"
        report_path.write_text(report, encoding="utf-8")
        C.info(f"恢复完成：错误 {len(errors)}，hash 失败 {len(failed)}，路径适配 {len(remapped)}；报告 {report_path}", opts.quiet)
        return 0 if not errors and not failed else 1
    finally:
        reader.close()


if __name__ == "__main__":
    sys.exit(main())
