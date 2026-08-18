#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ark_backup.py — 方舟备份（v3.0）

备份 Codex 与 WorkBuddy 的身份、技能、配置、记忆与自动化，生成：
- manifest.json      机器可读权威清单（恢复的唯一依据）
- RESTORE.md         给任何人/AI 的恢复协议（第一步就读它）
- secrets-notice.md  被排除/脱敏的敏感项清单与恢复后需重填的说明
- backup-summary.txt 人类可读摘要
- RECOMMEND.md       备份内容清单（决定/推荐/不建议）

用法：
  python ark_backup.py [--out PATH] [--zip] [--dry-run|--apply]
                        [--profile basic|advanced|full]
                        [--include-portable-credentials]
                        [--password-env NAME|--password-file FILE|--prompt-password]
                        [--dedupe none|keep-newest|skip|merge] [--to-desktop]
                        [--projects --projects-dirs DIR...]
                        [--compare <上次manifest.json>] [--quiet]

备份级别：
- basic（默认）：身份 + 技能 + 根级配置 + 记忆 + 自动化（精准白名单）
- advanced：在基础备份上增加连接器与项目索引，仍排除会话和敏感配置
- full：在中等备份上尽力增加本地可见的会话文件与索引；不保证客户端完整显示

可迁移敏感配置（--include-portable-credentials）：把已在所选范围内的用户自管配置值放入 AES 加密 ZIP。
账号登录文件、Cookie、系统钥匙串、DPAPI/设备绑定数据和云端 OAuth 授权始终排除；换机后按新设备流程重新登录。

去重（--dedupe）：技能二次识别后对重复技能（同名）的处理策略：
- none：全部保留，仅记录
- keep-newest：每组只保留修改时间最新的一份
- skip：每组只保留来源优先级最高的一份（codex > workbuddy > connector）
- merge：内容完全相同（hash 一致）的只留一份，不同的都保留并标记

输出位置：--out 指定，默认 ~/ark-backups/ark-YYYYMMDD-HHMMSS/；--to-desktop 把 zip 放桌面。
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ark_common as C

# ---------------------------------------------------------------------------
# Codex 根级白名单（advanced/full 时忽略，改全量扫描）
# ---------------------------------------------------------------------------

CODEX_ROOT_FILES = [
    "AGENTS.md", "AGENTS.override.md", "config.toml", "config.local.json",
    "hooks.json", "keybindings.json", "installation_id",
    "usage-log.json",
]
CODEX_ROOT_DIRS = [
    "skills", "memories", "automations", ".removed-skills",
]

WORKBUDDY_ROOT_FILES = [
    # 用户级人格/记忆文件（大写，WorkBuddy 根目录实际存在）
    "SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md",
    "settings.json", "models.json", "mcp.json", "mcp-approvals.json",
    "usage-log.json", ".connectors-marketplace.meta.json",
    "device-id", ".mcp.json",
    # 注意：WorkBuddy 没有用户级 AGENTS.md（项目级在工作区根目录，见项目备份段）
]
WORKBUDDY_ROOT_DIRS = [
    "skills", "connectors", "memory", "_disabled_skills",
]

CONNECTORS_SUB_FILES = ["mcp.json", "connector-states.v3.json"]

# 来源优先级（--dedupe skip 用）
SOURCE_PRIORITY = {"codex": 0, "workbuddy": 1, "workbuddy-connector": 2, "project": 3}

PROFILE_LABELS = {
    "basic": "基础备份（身份、技能、设置、记忆、自动化；不含会话与敏感配置）",
    "advanced": "中等备份（在基础上增加连接器与项目索引；不含会话与敏感配置）",
    "full": "全量备份（在中等上增加本地会话文件与索引；敏感配置另行确认）",
}

# ---------------------------------------------------------------------------
# 文件收集
# ---------------------------------------------------------------------------


class Collector:
    def __init__(self, manifest: dict, opts, skip_dirs: set, include_secrets: bool):
        self.m = manifest
        self.opts = opts
        self.skip_dirs = skip_dirs
        self.include_secrets = include_secrets
        self.entry_count = 0

    # -- 用户自管敏感配置判定；账号登录与设备绑定状态由独立规则始终排除 --
    def _is_secret(self, p: Path) -> bool:
        name = p.name
        if name in C.SECRET_FILE_NAMES:
            return True
        for pat in C.SECRET_FILE_PATTERNS:
            if pat.match(name):
                return True
        for part in p.parts:
            if part in C.SECRET_DIRS:
                return True
        return False

    def classify(self, path: Path, rel_dir: str) -> str | None:
        """返回 'skill-file' / 'config' / 'memory' / 'automation' / 'project' / 'identity' / 'other'，排除则 None。"""
        name = path.name
        for pat in C.RUNTIME_FILE_PATTERNS:
            if pat.match(name):
                return None
        if name == "SKILL.md":
            return "skill-file"
        if rel_dir.startswith("codex/memories") or rel_dir.startswith("workbuddy/memory"):
            return "memory"
        if "automations" in rel_dir:
            return "automation"
        if rel_dir.startswith("workbuddy/projects"):
            return "project"
        if name in {"SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md"}:
            return "identity"
        if C.file_kind(path) == "config":
            return "config"
        return "other"

    def record_skill(self, p: Path, rel_prefix: str, source: str):
        skill = C.detect_skill(p)
        if skill:
            self.m["skills"].append({
                "name": skill["frontmatterName"] or p.name,
                "source": source,
                "relPath": rel_prefix + "/" + p.name,
                "originPath": str(p),
                **skill,
            })

    def walk_tree(self, root: Path, rel_prefix: str, source: str, max_size: int, extra_skip: set[str] | None = None):
        """递归收集。跳过运行时目录，识别技能目录。"""
        skip = self.skip_dirs | (extra_skip or set())
        try:
            entries = sorted(os.scandir(root), key=lambda e: e.name)
        except OSError as e:
            C.warn(f"无法读取目录 {root}: {e}", self.opts.quiet)
            return
        for ent in entries:
            p = Path(ent.path)
            if ent.is_dir():
                if p.name in skip:
                    self.record_excluded(p, "runtime-or-sensitive-dir")
                    continue
                if C.detect_skill(p):
                    self.record_skill(p, rel_prefix, source)
                self.walk_tree(p, rel_prefix + "/" + p.name, source, max_size, extra_skip)
            else:
                in_session = source == "codex" and ("sessions" in rel_prefix or "archived_sessions" in rel_prefix)
                self.collect_file(p, rel_prefix, source, max_size, allow_session=in_session)

    def collect_file(self, p: Path, rel_prefix: str, source: str, max_size: int,
                     allow_jsonl: bool = False, allow_session: bool = False):
        """allow_jsonl=True 时放行 .jsonl（用于项目对话记录，用户显式要求备份）。
        allow_session=True 时放行 Codex 会话正文与索引（full 档：rollout-*.jsonl、
        session_index.jsonl、state_*.sqlite，索引文件名随版本变化，按实际存在匹配）。"""
        try:
            size = p.stat().st_size
        except OSError as e:
            C.warn(f"无法 stat {p}: {e}", self.opts.quiet)
            return
        if max_size and size > max_size:
            self.record_excluded(p, f"larger-than-{max_size}")
            return
        name = p.name
        rel = rel_prefix + "/" + name
        if C.is_account_state(p):
            self.record_excluded(p, "account-login-cookie-or-device-bound")
            return
        if not (allow_jsonl and name.endswith(".jsonl")) and not (
            allow_session
            and (name.endswith(".jsonl") or name.endswith(".sqlite")
                 or name.endswith(".sqlite-shm") or name.endswith(".sqlite-wal")
                 or name.endswith(".db") or name.endswith(".db-shm") or name.endswith(".db-wal"))):
            for pat in C.RUNTIME_FILE_PATTERNS:
                if pat.match(name):
                    self.record_excluded(p, "runtime-file")
                    return
        is_secret = self._is_secret(p)
        if is_secret and not self.include_secrets:
            self.record_excluded(p, "secret-file")
            return
        if is_secret:
            kind = "secret"
        elif allow_session:
            kind = "conversation"  # Codex 会话正文/索引（full 档）
        elif allow_jsonl and name.endswith(".jsonl"):
            kind = "conversation"  # 项目对话记录
        else:
            kind = self.classify(p, rel_prefix)
            if kind is None:
                self.record_excluded(p, "runtime-file")
                return
        lt = C.link_target(p)
        try:
            digest = C.sha256_file(p) if lt is None else None
        except PermissionError:
            C.warn(f"无法读取（占用/权限）已跳过: {p}", self.opts.quiet)
            self.record_excluded(p, "runtime-file")
            return
        entry = {
            "relPath": rel,
            "originPath": str(p),
            "source": source,
            "size": size,
            "sha256": digest,
            "type": kind,
            "linkTarget": lt,
        }
        if is_secret:
            entry["secret"] = True  # 用户自管敏感配置：原样进入 AES 包，不做脱敏
        self.m["entries"].append(entry)
        self.entry_count += 1

        # 敏感值扫描与脱敏
        # 默认：配置文件中的敏感值（API KEY、MCP headers、token 等）脱敏为 ${KEY} 占位符
        # 可迁移敏感配置模式：所选配置内容原样进入 AES ZIP；账号登录状态始终排除
        if lt is None and size > 0 and size < 4 * 1024 * 1024 and not is_secret:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if C.should_redact_file(p):
                redacted, replaced = C.redact_file_content(p, text)
                if replaced:
                    if self.include_secrets:
                        # 用户确认后保留敏感配置值，仅记录本会脱敏的键
                        self.m["keptSecrets"].append({
                            "relPath": rel,
                            "keysKept": replaced,
                        })
                        entry["keptSecretValues"] = True
                    else:
                        self.m["sanitized"].append({
                            "relPath": rel,
                            "keysReplaced": replaced,
                        })
                        entry["sanitized"] = True
                        # 备份中实际存储的是脱敏版：sha256 必须以脱敏后内容为准
                        entry["originSha256"] = entry["sha256"]
                        entry["sha256"] = hashlib.sha256(redacted.encode("utf-8")).hexdigest()
            else:
                hits = C.scan_secret_in_text(text)
                if hits:
                    self.m["suspicious"].append({
                        "relPath": rel,
                        "matches": hits[:5],
                    })

    def record_excluded(self, p: Path, reason: str):
        try:
            size = p.stat().st_size
        except OSError:
            size = None
        self.m["excluded"].append({
            "originPath": str(p),
            "reason": reason,
            "size": size,
        })

    def collect_root_files(self, root: Path, rel_prefix: str, source: str, allow: set[str], max_size: int):
        """根级白名单文件。allow 为空 → 收集所有非排除文件。"""
        try:
            entries = sorted(os.scandir(root), key=lambda e: e.name)
        except OSError:
            return
        for ent in entries:
            p = Path(ent.path)
            if ent.is_dir():
                if p.name in self.skip_dirs:
                    self.record_excluded(p, "runtime-or-sensitive-dir")
                    continue
                if p.name == "connectors" and source == "workbuddy":
                    self.collect_connectors(p, max_size)
                    continue
                if allow and p.name not in allow:
                    # 用户自管敏感配置目录不在白名单时，仅在单独确认后放行
                    if not (self.include_secrets and p.name in C.SECRET_DIRS):
                        continue
                if C.detect_skill(p):
                    self.record_skill(p, rel_prefix, source)
                self.walk_tree(p, rel_prefix + "/" + p.name, source, max_size)
            else:
                if allow and p.name not in allow:
                    if not (self.include_secrets and self._is_secret(p)):
                        continue
                codex_session_index = (
                    source == "codex"
                    and self.opts.profile == "full"
                    and (p.name == "session_index.jsonl" or re.match(r"^state_.*\.(sqlite|db)(-(shm|wal))?$", p.name))
                )
                self.collect_file(p, rel_prefix, source, max_size, allow_session=bool(codex_session_index))

    def collect_connectors(self, root: Path, max_size: int):
        """connectors/：收集白名单配置与技能；账号登录、Cookie 和设备绑定文件始终排除。"""
        for ent in sorted(os.scandir(root), key=lambda e: e.name):
            p = Path(ent.path)
            if ent.is_dir():
                if p.name in self.skip_dirs:
                    self.record_excluded(p, "runtime-or-sensitive-dir")
                    continue
                if p.name in {"skills"}:
                    for sub in sorted(os.scandir(p), key=lambda e: e.name):
                        sp = Path(sub.path)
                        if sub.is_dir():
                            if C.detect_skill(sp):
                                self.record_skill(sp, "workbuddy/connectors/skills", "workbuddy-connector")
                            self.walk_tree(sp, "workbuddy/connectors/skills/" + sp.name, "workbuddy-connector", max_size)
                elif p.name == "default":
                    self.collect_root_files(p, "workbuddy/connectors/default", "workbuddy", set(CONNECTORS_SUB_FILES), max_size)
                else:
                    # uuid 目录：只收声明过的配置；账号登录与设备绑定文件始终排除
                    for sub in sorted(os.scandir(p), key=lambda e: e.name):
                        sp = Path(sub.path)
                        if sp.is_file() and sp.name in {"mcp.json", "connector-states.v3.json"}:
                            self.collect_file(sp, "workbuddy/connectors/" + p.name, "workbuddy", max_size)
                        elif sp.is_file() and self._is_secret(sp) and self.include_secrets:
                            self.collect_file(sp, "workbuddy/connectors/" + p.name, "workbuddy", max_size)
                        elif sp.is_dir():
                            if sp.name in self.skip_dirs:
                                self.record_excluded(sp, "runtime-or-sensitive-dir")
            elif p.name == "mcp.json":
                self.collect_file(p, "workbuddy/connectors", "workbuddy", max_size)


# ---------------------------------------------------------------------------
# 技能去重（二次识别）
# ---------------------------------------------------------------------------


def apply_dedupe(manifest: dict, mode: str, quiet: bool) -> None:
    """对同名技能应用去重策略。修改 manifest['skills'] 与 manifest['entries']。"""
    if mode == "none":
        return
    groups: dict[str, list] = {}
    for sk in manifest["skills"]:
        groups.setdefault(sk["name"], []).append(sk)
    dups = {n: g for n, g in groups.items() if len(g) > 1}
    if not dups:
        return
    decisions: list[dict] = []
    removed_skills: list = []
    removed_prefixes: list[str] = []

    def remove_skill(sk: dict):
        removed_skills.append(sk)
        removed_prefixes.append(sk["relPath"] + "/")
        manifest["skills"].remove(sk)

    for name, group in dups.items():
        if mode == "keep-newest":
            def mtime(sk):
                try:
                    return os.stat(sk["originPath"]).st_mtime
                except OSError:
                    return 0
            group.sort(key=mtime, reverse=True)
            keep = group[0]
            for sk in group[1:]:
                decisions.append({"name": name, "kept": keep["relPath"], "dropped": sk["relPath"], "reason": "older-mtime"})
                remove_skill(sk)
        elif mode == "skip":
            group.sort(key=lambda s: SOURCE_PRIORITY.get(s["source"], 9))
            keep = group[0]
            for sk in group[1:]:
                decisions.append({"name": name, "kept": keep["relPath"], "dropped": sk["relPath"], "reason": "lower-source-priority"})
                remove_skill(sk)
        elif mode == "merge":
            # 内容完全相同（同 relPath 同 sha256）才去重；不同保留并标记
            def signature(sk):
                sig = set()
                for e in manifest["entries"]:
                    if e["relPath"].startswith(sk["relPath"] + "/"):
                        sig.add((e["relPath"][len(sk["relPath"]):], e["sha256"]))
                return frozenset(sig)
            unique: list = []
            for sk in group:
                s = signature(sk)
                if any(s == signature(u) for u in unique):
                    decisions.append({"name": name, "kept": unique[0]["relPath"], "dropped": sk["relPath"], "reason": "identical-content"})
                    remove_skill(sk)
                else:
                    unique.append(sk)
            manifest["duplicates"] = manifest.get("duplicates", {})
            for sk in unique:
                manifest["duplicates"].setdefault(name, []).append(sk["relPath"])

    manifest["dedupe"] = {"mode": mode, "decisions": decisions, "removedSkills": len(removed_skills)}
    for prefix in removed_prefixes:
        manifest["entries"] = [e for e in manifest["entries"] if not e["relPath"].startswith(prefix)]
    if not quiet:
        C.info(f"去重({mode})：移除 {len(removed_skills)} 个重复技能、{sum(1 for _ in removed_prefixes)} 组文件")


# ---------------------------------------------------------------------------
# 自动化导出（workbuddy.db 只读）
# ---------------------------------------------------------------------------


def export_workbuddy_automations(wb_home: Path, quiet: bool) -> dict:
    db = wb_home / "workbuddy.db"
    result = {"source": str(db), "exported": False, "count": 0, "error": None}
    if not db.is_file():
        return result
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        cur = con.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(automations)").fetchall()]
        rows = cur.execute(
            "SELECT * FROM automations WHERE deleted_at IS NULL"
        ).fetchall()
        records = [dict(zip(cols, r)) for r in rows]
        drop = {"owner_user_id", "owner_status", "owner_source", "updated_at"}
        for rec in records:
            for k in drop:
                rec.pop(k, None)
        result["exported"] = True
        result["count"] = len(records)
        result["records"] = records
        con.close()
    except Exception as e:
        result["error"] = str(e)
        C.warn(f"workbuddy.db 自动化导出失败: {e}", quiet)
    return result


def export_codex_automations(codex_home: Path) -> dict:
    d = codex_home / "automations"
    if not d.is_dir():
        return {"found": False, "count": 0}
    n = sum(1 for p in d.rglob("*") if p.is_file())
    return {"found": True, "count": n}


def resolve_password(opts) -> str | None:
    """从不会默认暴露在命令历史里的来源读取备份口令。"""
    choices = [bool(opts.zip_password), bool(opts.password_file), bool(opts.password_env), bool(opts.prompt_password)]
    if sum(choices) > 1:
        raise SystemExit("口令来源只能选一种：--password-file / --password-env / --prompt-password")
    if opts.zip_password:
        C.warn("--zip-password 仅为旧版兼容，可能泄露到命令历史；建议使用 --password-env 或隐藏输入。")
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


def refresh_stats(manifest: dict) -> None:
    entries = manifest["entries"]
    stats = manifest["stats"]
    stats["fileCount"] = len(entries)
    stats["totalBytes"] = sum(e.get("size") or 0 for e in entries)
    stats["excludedCount"] = len(manifest["excluded"])
    stats["sanitizedCount"] = len(manifest["sanitized"])
    stats["suspiciousCount"] = len(manifest["suspicious"])
    stats["secretCount"] = sum(1 for e in entries if e.get("secret"))
    stats["entryTypes"] = {}
    for entry in entries:
        kind = entry["type"]
        stats["entryTypes"][kind] = stats["entryTypes"].get(kind, 0) + 1


def preflight_sources(manifest: dict) -> None:
    """写入前再次核对源文件；扫描后变化就停止，避免得到自相矛盾的快照。"""
    failures = []
    for entry in manifest["entries"]:
        if entry.get("linkTarget") is not None:
            continue
        source = Path(entry["originPath"])
        if not source.is_file():
            failures.append(f"源文件已消失: {entry['relPath']}")
            continue
        try:
            if entry.get("sanitized"):
                text = source.read_text(encoding="utf-8")
                redacted, _ = C.redact_file_content(source, text)
                digest = hashlib.sha256(redacted.encode("utf-8")).hexdigest()
            else:
                digest = C.sha256_file(source)
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"无法复核 {entry['relPath']}: {exc}")
            continue
        if digest != entry.get("sha256"):
            failures.append(f"扫描后发生变化: {entry['relPath']}")
    if failures:
        sample = "\n".join(f"- {item}" for item in failures[:20])
        raise SystemExit(f"写入前复核未通过，未创建备份。请重新扫描：\n{sample}")


def generated_files(manifest: dict) -> dict[str, bytes]:
    result = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        "RESTORE.md": render_restore_md(manifest).encode("utf-8"),
        "secrets-notice.md": render_secrets_notice(manifest).encode("utf-8"),
        "RECOMMEND.md": render_recommendations(manifest).encode("utf-8"),
        "backup-summary.txt": render_summary(manifest).encode("utf-8"),
    }
    automation = manifest["automations"].get("workbuddy", {})
    if automation.get("exported"):
        result["workbuddy/automations.json"] = json.dumps(
            automation, ensure_ascii=False, indent=2
        ).encode("utf-8")
    return result


def write_entry_to_directory(entry: dict, target: Path) -> None:
    if entry.get("linkTarget") is not None:
        return
    source = Path(entry["originPath"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if entry.get("sanitized"):
        text = source.read_text(encoding="utf-8")
        redacted, _ = C.redact_file_content(source, text)
        target.write_bytes(redacted.encode("utf-8"))
    else:
        shutil.copy2(source, target)


def write_directory_backup(out_dir: Path, manifest: dict) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"输出目录非空，为避免覆盖已停止: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for entry in manifest["entries"]:
        write_entry_to_directory(entry, out_dir / Path(*entry["relPath"].split("/")))
    for rel, data in generated_files(manifest).items():
        target = out_dir / Path(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def write_zip_backup(zip_path: Path, manifest: dict, password: str | None) -> None:
    """直接从源文件写 ZIP，不创建含敏感配置的明文暂存目录。"""
    if zip_path.exists():
        raise SystemExit(f"输出文件已存在，为避免覆盖已停止: {zip_path}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = bool(password)
    if manifest["options"].get("includeSecrets") and not encrypted:
        raise SystemExit("包含敏感配置时必须提供 AES 口令；未创建备份。")
    if encrypted:
        try:
            import pyzipper  # type: ignore
        except ImportError as exc:
            raise SystemExit("缺少 pyzipper，不能安全创建 AES 加密包；未降级、未创建明文备份。") from exc
        factory = lambda: pyzipper.AESZipFile(
            zip_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        )
    else:
        factory = lambda: zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED)
    try:
        with factory() as archive:
            if encrypted:
                archive.setpassword(password.encode("utf-8"))
            for entry in manifest["entries"]:
                if entry.get("linkTarget") is not None:
                    continue
                source = Path(entry["originPath"])
                rel = entry["relPath"]
                if entry.get("sanitized"):
                    text = source.read_text(encoding="utf-8")
                    redacted, _ = C.redact_file_content(source, text)
                    archive.writestr(rel, redacted.encode("utf-8"))
                else:
                    archive.write(source, rel)
            for rel, data in generated_files(manifest).items():
                archive.writestr(rel, data)
    except Exception:
        failed = zip_path.with_suffix(zip_path.suffix + ".failed")
        if zip_path.exists() and not failed.exists():
            zip_path.replace(failed)
        raise


# ---------------------------------------------------------------------------
# 备份包生成
# ---------------------------------------------------------------------------


def render_restore_md(manifest: dict) -> str:
    s = manifest["stats"]
    opts = manifest.get("options", {})
    include_secrets = opts.get("includeSecrets", False)
    profile = opts.get("profile", "basic")
    lines = [
        "# 恢复指南（RESTORE.md）",
        "",
        "这是由 `ark`（灵魂方舟）技能生成的 AI 环境备份包。**任何 AI 或人恢复本备份时，必须先读本文件，再读 `manifest.json`。**",
        "",
        "## 这是什么",
        "",
        f"- 备份时间：{manifest['createdAt']}",
        f"- 备份工具：{manifest['tool']['name']} {manifest['tool']['version']}（schema {manifest['schemaVersion']}）",
        f"- 备份级别：{PROFILE_LABELS.get(profile, profile)}",
        f"- 可迁移敏感配置：{'已放入 AES 加密包' if include_secrets else '未包含；敏感值已脱敏'}",
        f"- 文件数：{s.get('fileCount', 0)}，总大小：{C.size_str(s.get('totalBytes', 0))}",
        f"- 技能数：{s.get('skillCount', 0)}（Codex {s.get('codexSkills', 0)} / WorkBuddy {s.get('workbuddySkills', 0)} / 连接器 {s.get('connectorSkills', 0)}）",
        f"- 自动化：Codex {s.get('codexAutomations', 0)} 项，WorkBuddy {s.get('workbuddyAutomations', 0)} 项",
        f"- 被排除：{s.get('excludedCount', 0)} 项（运行时/账号状态/超大文件）",
        f"- 脱敏：{s.get('sanitizedCount', 0)} 个文件（敏感值已替换为 ${{KEY}} 占位符）",
        "",
        "## 目录结构",
        "",
        "```",
        "backup/",
        "├── manifest.json        # 权威清单：每个文件、hash、来源、元数据",
        "├── RESTORE.md           # 本文件",
        "├── secrets-notice.md    # 敏感项说明",
        "├── RECOMMEND.md         # 备份内容清单（决定/推荐/不建议）",
        "├── backup-summary.txt   # 人类可读摘要",
        "├── codex/               # → 恢复到 ~/.codex/（或 $CODEX_HOME）",
        "├── workbuddy/           # → 恢复到 ~/.workbuddy/（或 $WORKBUDDY_HOME）",
        "│   └── automations.json # WorkBuddy 自动化定义（默认不自动写库）",
        "└── projects/            # 项目级 .workbuddy 数据（默认不自动恢复）",
        "```",
        "",
        "## 恢复步骤（推荐顺序）",
        "",
        "1. **读 manifest**：`python ark_restore.py <backup> --dry-run` 查看将覆盖/新增/冲突的完整清单。",
        "2. **确认范围**：默认只恢复 `codex` 与 `workbuddy` 两部分；`projects` 需要人工确认项目路径。",
        "3. **执行恢复**：`python ark_restore.py <backup> --apply`。被覆盖的旧文件会先移入目标用户目录下的 `~/.ark/restore-conflicts/`。",
        "4. **校验**：恢复脚本先按 manifest 核对源内容，报告写入目标用户目录下的 `~/.ark/restore-reports/`。",
        "5. **敏感配置**：打开 `secrets-notice.md` 按清单处理。",
        "6. **账号登录**：账号状态与设备授权不会迁移，按新设备流程重新登录。",
        "",
    ]
    if include_secrets:
        lines += [
            "## 本备份包含用户确认的敏感配置",
            "",
            "用户确认后，所选范围内的用户自管配置值会直接写入 AES 加密 ZIP，不经过明文暂存目录。",
            "账号登录文件、Cookie、系统钥匙串、DPAPI/设备绑定数据与云端 OAuth 授权始终排除，",
            "换机后按新设备流程重新登录（见 secrets-notice.md）。",
            "",
        ]
    lines += [
        "## 自动化恢复（特殊处理）",
        "",
        "- **WorkBuddy 自动化**只读导出为 `workbuddy/automations.json`。恢复时生成待办计划，必须由 AI 通过 WorkBuddy 官方自动化接口逐项创建并回读；禁止直写 `workbuddy.db`。",
        "- **Codex 自动化**为目录结构（`automation.toml` + `memory.md`），随 `codex/` 部分直接恢复。",
        "",
        "## 平台差异",
        "",
        "| 备份内路径 | Linux/macOS | Windows |",
        "| --- | --- | --- |",
        "| `codex/` | `~/.codex/`（或 `$CODEX_HOME`） | `%USERPROFILE%\\.codex\\` |",
        "| `workbuddy/` | `~/.workbuddy/` | `%USERPROFILE%\\.workbuddy\\` |",
        "| 配置中的旧用户绝对路径 | 恢复脚本自动适配并报告 | 恢复脚本自动适配并报告 |",
        "",
        "注意：恢复脚本会适配已知配置中的旧用户主目录；指向外置盘、项目盘或自定义软件目录的路径仍需健康检查。",
        "",
        "## 恢复后自检",
        "",
        "- 技能：`ls ~/.codex/skills/` 与 `ls ~/.workbuddy/skills/` 数量与 `backup-summary.txt` 一致",
        "- 身份：`~/.workbuddy/SOUL.md` / `IDENTITY.md` / `USER.md` / `MEMORY.md` 存在",
        "- 自动化：Codex 侧 `~/.codex/automations/` 完整；WorkBuddy 侧检查「自动化」页面",
        "- 敏感配置：检查已恢复的配置值是否生效；账号与设备授权按新设备流程重新登录",
        "- 校验：`restore-report.md` 中无 `校验失败` 与 `错误` 节",
    ]
    return "\n".join(lines)


def render_secrets_notice(manifest: dict) -> str:
    include_secrets = manifest.get("options", {}).get("includeSecrets", False)
    lines = [
        "# 敏感配置说明（secrets-notice.md）",
        "",
    ]
    if include_secrets:
        secret_files = [e for e in manifest["entries"] if e.get("secret")]
        kept = manifest.get("keptSecrets", [])
        lines += [
            "本备份已包含用户确认的**可迁移敏感配置**，内容位于 AES 加密 ZIP 中。",
            "ZIP 文件名和成员路径仍可能可见；请只保存在可信位置，不要上传公开仓库或聊天群。",
            "",
            "## 1. 原样打包的敏感配置文件",
            "",
        ]
        if secret_files:
            for e in secret_files:
                lines.append(f"- `{e['relPath']}`（来源 {e['source']}）")
        else:
            lines.append("-（无独立敏感配置文件）")
        lines += [
            "",
            "## 2. 配置文件中原样保留的敏感值（未脱敏）",
            "",
        ]
        if kept:
            for k in kept:
                keys = ", ".join(k["keysKept"])
                lines.append(f"- `{k['relPath']}` → 保留：{keys}")
        else:
            lines.append("-（无）")
        lines += [
            "",
            "## 3. 仍需手动处理的项（文件里拿不到的部分）",
            "",
            "- 系统环境变量（MCP headers 中 `${ENV}` 引用的值、`config.toml` 的 `env_vars`）：换机后需在目标机设置同名环境变量",
            "- 系统钥匙串、DPAPI 或设备绑定登录态：无法保证跨设备读取，需要重新登录",
            "- WorkBuddy 连接器的云端授权（OAuth 回调）：可能需重新授权",
            "",
        ]
    else:
        lines += ["本备份包**不含敏感配置值**，恢复后需要按清单重新填写。", ""]
    lines += [
        "## 4. 被排除的敏感文件（未备份）",
        "",
        "| 路径 | 原因 |",
        "| --- | --- |",
    ]
    secret_reasons = {"secret-file", "runtime-or-sensitive-dir"}
    shown = False
    for e in manifest["excluded"]:
        if e["reason"] in secret_reasons:
            lines.append(f"| `{e['originPath']}` | {e['reason']} |")
            shown = True
    if not shown:
        lines.append("|（无） | |")
    lines += [
        "",
        "## 5. 脱敏的配置文件（敏感值已替换为占位符）",
        "",
        "以下文件的敏感值已替换为 `${KEY}` 占位符，恢复后必须重新填入真实值：",
        "",
    ]
    if manifest["sanitized"]:
        for s in manifest["sanitized"]:
            keys = ", ".join(s["keysReplaced"])
            lines.append(f"- `{s['relPath']}` → 需重填：{keys}")
    else:
        lines.append("-（无）")
    lines += [
        "",
        "## 6. 含疑似敏感值的普通文件（已原样备份，注意保管备份包）",
        "",
    ]
    if manifest["suspicious"]:
        for s in manifest["suspicious"]:
            lines.append(f"- `{s['relPath']}`：命中 {len(s['matches'])} 类高置信模式（报告不保存疑似敏感值原文）")
    else:
        lines.append("-（无）")
    lines += [
        "",
        "## 7. 保管建议",
        "",
        "- 本备份含个人身份与技能内容，请存放在可信位置（私有仓库/加密盘）。",
        "- 含敏感配置的备份不得公开分享；方舟只允许生成 AES 加密 ZIP。",
    ]
    return "\n".join(lines)


def render_recommendations(manifest: dict) -> str:
    """第三步入库：决定备份 / 推荐备份 / 建议不备份 三张清单。"""
    s = manifest["stats"]
    opts = manifest.get("options", {})
    profile = opts.get("profile", "basic")
    et = s.get("entryTypes", {})
    lines = [
        "# 备份内容清单（RECOMMEND.md）",
        "",
        f"备份级别：{profile}",
        "",
        "## (a) 决定备份的内容",
        "",
        f"- 身份文件：4 个（SOUL.md / IDENTITY.md / USER.md / MEMORY.md）",
        f"- 技能：{s.get('skillCount', 0)} 个（codex {s.get('codexSkills', 0)}、workbuddy {s.get('workbuddySkills', 0)}、connector {s.get('connectorSkills', 0)}），含 SKILL.md 及 scripts/references/assets",
        f"- 配置：{et.get('config', 0)} 个（config.toml、settings.json、mcp.json、hooks.json 等，命中敏感值已脱敏）",
        f"- 记忆：{et.get('memory', 0)} 个（memories/ 与 memory/ 下的长期记忆文件）",
        f"- 自动化：Codex {s.get('codexAutomations', 0)} 项 + WorkBuddy {s.get('workbuddyAutomations', 0)} 项",
        f"- 项目元数据：{et.get('project', 0)} 个（workbuddy/projects 路径索引）",
        "",
        "## (b) 推荐备份的内容",
        "",
        "- 连接器配置（connectors/ 的 mcp.json 与技能）——已包含",
        "- 自动化任务（automations）——已包含",
        "- 技能中的可执行脚本与资源（scripts/references/assets）——已包含",
        "- 项目级 `.workbuddy/` 数据（`--projects --projects-dirs`）——**当前未选**，含项目内记忆与规则",
        "- 可迁移敏感配置（`--include-portable-credentials`）——需单独确认，只能进入 AES 加密 ZIP",
        "",
        "## (c) 建议不备份的内容",
        "",
        "- 会话历史（sessions / archived_sessions）：体积可能较大且含隐私；只有全量备份才纳入。能归档不等于新版本客户端一定能继续显示或续聊。",
        "- 日志与缓存（logs、cache、blobs、*.sqlite*、*.tmp）：运行时产物，自动重建，备份无意义。",
        "- 账号登录与设备授权（钥匙串、OAuth 会话）：不在备份范围内，换机后重新登录。",
        "- 插件市场缓存（plugins/、connectors-marketplace/）：可重新下载安装。",
        "- 超大文件（>100MB）：默认跳过，`--max-file-size` 可调。",
        "",
        "## 去重说明",
        "",
    ]
    if manifest.get("dedupe"):
        d = manifest["dedupe"]
        lines.append(f"去重模式：{d['mode']}，移除 {d['removedSkills']} 个重复技能：")
        for dec in d["decisions"]:
            lines.append(f"- `{dec['name']}`：保留 `{dec['kept']}`，丢弃 `{dec['dropped']}`（{dec['reason']}）")
    else:
        lines.append("去重模式：none（未处理）。重复技能清单见 manifest.json 的 skills 分组，可用 --dedupe keep-newest/skip/merge 处理。")
    return "\n".join(lines)


def render_summary(manifest: dict) -> str:
    s = manifest["stats"]
    opts = manifest.get("options", {})
    lines = [
        f"ark 备份摘要 — {manifest['createdAt']}",
        f"级别 {PROFILE_LABELS.get(opts.get('profile', 'basic'), opts.get('profile', 'basic'))}、敏感配置 {'含（AES）' if opts.get('includeSecrets') else '不含'}、去重 {opts.get('dedupe', 'none')}",
        f"文件 {s.get('fileCount', 0)} 个 / {C.size_str(s.get('totalBytes', 0))}",
        f"技能 {s.get('skillCount', 0)} 个（codex {s.get('codexSkills', 0)}、workbuddy {s.get('workbuddySkills', 0)}、connector {s.get('connectorSkills', 0)}）",
        f"自动化 codex {s.get('codexAutomations', 0)}、workbuddy {s.get('workbuddyAutomations', 0)}",
        f"敏感配置文件 {s.get('secretCount', 0)}、排除 {s.get('excludedCount', 0)}、脱敏 {s.get('sanitizedCount', 0)}、可疑 {s.get('suspiciousCount', 0)}",
        "",
        "来源：",
    ]
    for k, v in manifest["sources"].items():
        lines.append(f"  {k}: {v.get('home', '?')} (found={v.get('found')})")
    lines.append("")
    lines.append("技能清单：")
    for sk in manifest["skills"]:
        flag = "" if sk.get("dirNameMatches") else " ⚠️ 目录名与 frontmatter name 不一致"
        created = "（自建）" if sk.get("agentCreated") else ""
        lines.append(f"  [{sk['source']}] {sk['name']}{created}{flag}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="方舟备份：Codex + WorkBuddy 可迁移快照")
    ap.add_argument("--out", help="输出目录或 .zip 路径（默认 ~/ark-backups/ark-<时间戳>）")
    ap.add_argument("--zip", action="store_true", help="直接写 zip，不创建明文暂存目录")
    ap.add_argument("--zip-password", help="旧版兼容：直接传口令（不推荐）")
    ap.add_argument("--password-file", help="从文件读取 AES 口令")
    ap.add_argument("--password-env", help="从指定环境变量读取 AES 口令")
    ap.add_argument("--prompt-password", action="store_true", help="隐藏输入 AES 口令")
    ap.add_argument("--to-desktop", action="store_true", help="把 zip 输出到桌面（隐含 --zip）")
    ap.add_argument("--keep", type=int, help="旧版兼容：不再自动删除旧备份，仅提示人工整理")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只扫描与统计，不写任何文件（默认）")
    mode.add_argument("--apply", action="store_true", help="执行备份写入")
    ap.add_argument("--profile", choices=["basic", "advanced", "full"], default="basic",
                    help="基础备份 / 中等备份 / 全量备份（内部值 basic/advanced/full）")
    ap.add_argument("--include-sensitive-config", "--include-portable-credentials", "--include-secrets", dest="include_secrets",
                    action="store_true", help="包含所选范围内的用户自管敏感配置；账号登录状态仍排除；强制 AES ZIP")
    ap.add_argument("--dedupe", choices=["none", "keep-newest", "skip", "merge"], default="none",
                    help="重复技能处理：keep-newest（留最新）/ skip（留来源优先）/ merge（内容相同才去重）")
    ap.add_argument("--projects", action="store_true",
                    help="备份项目级数据（项目根 AGENTS.md/CLAUDE.md + .workbuddy 记忆/日志 + 会话对话记录）。"
                         "不带 --projects-dirs 时自动发现用过哪些项目（--list-projects 可预览）")
    ap.add_argument("--projects-dirs", nargs="*", help="要备份的项目目录列表（也可用 auto 自动发现全部存在项目）")
    ap.add_argument("--list-projects", action="store_true", help="列出发现的使用过的项目文件夹，供用户确认/补充")
    ap.add_argument("--json", action="store_true", help="--list-projects 时输出 JSON")
    ap.add_argument("--max-file-size", type=int, default=100, help="单文件大小上限 MB（默认 100，0=不限）")
    ap.add_argument("--compare", help="与此 manifest.json 对比，输出变更摘要")
    ap.add_argument("--quiet", action="store_true", help="减少输出")
    opts = ap.parse_args()

    if opts.keep is not None:
        C.warn("--keep 不再自动删除旧备份。请在确认准确路径与恢复方式后手动整理。", opts.quiet)

    # --list-projects：只列出发现的项目，供用户确认/补充（不备份）
    if opts.list_projects:
        projects = C.discover_projects(quiet=opts.quiet)
        if opts.json:
            print(json.dumps(projects, ensure_ascii=False, indent=2))
            return 0
        existing = [p for p in projects if p["exists"]]
        missing = [p for p in projects if not p["exists"]]
        print("== 使用过的项目文件夹（备份前请确认，可在下方补充缺失的）==")
        for i, pr in enumerate(existing, 1):
            src = "/".join(pr["sources"])
            line = (f"{i:2}. [{pr['path']}]  (来源: {src})")
            extra = []
            if pr["wbConversations"]:
                extra.append(f"会话 {pr['wbConversations']} 条")
            if pr["memoryLogs"]:
                extra.append(f"每日日志 {pr['memoryLogs']} 篇")
            if pr["hasAgentsMd"]:
                extra.append("AGENTS.md")
            if pr["hasClaudeMd"]:
                extra.append("CLAUDE.md")
            if extra:
                line += "  · " + "、".join(extra)
            print(line)
        if missing:
            n_tmp = sum(1 for p in missing if "\\default\\" in p["path"].replace("/", "\\").lower()
                        or "\\default-" in p["path"].replace("/", "\\").lower())
            n_real = len(missing) - n_tmp
            if n_tmp:
                print(f"\n另有 {n_tmp} 个临时工作区索引（default-*，路径已清理，不备份）")
            if n_real:
                print(f"\n另有 {n_real} 个历史索引路径不存在（可能已移动/删除）：")
                for p in missing:
                    if not ("\\default\\" in p["path"].replace("/", "\\").lower()
                            or "\\default-" in p["path"].replace("/", "\\").lower()):
                        print(f"  - {p['path']}")
                print("若其中项目仍存在（路径变了），请用 --projects-dirs 补充真实路径。")
        print(f"\n确认后备份：ark_backup.py --projects（自动包含以上 {len(existing)} 个存在项目）")
        return 0

    codex = C.codex_home()
    wb = C.workbuddy_home()
    include_session = opts.profile == "full"
    include_secrets = opts.include_secrets
    everything = opts.profile in ("advanced", "full")

    manifest = C.ensure_manifest_structure({})
    manifest["sources"] = {
        "codex": {"home": str(codex), "found": codex.is_dir()},
        "workbuddy": {"home": str(wb), "found": wb.is_dir()},
    }
    manifest["options"] = {
        "profile": opts.profile,
        "profileLabel": PROFILE_LABELS[opts.profile],
        "includeSecrets": include_secrets,
        "dedupe": opts.dedupe,
        "zipEncrypted": False,
    }
    max_size = opts.max_file_size * 1024 * 1024
    skip_dirs = C.default_skip_dirs(include_session=include_session, include_secrets=include_secrets)
    col = Collector(manifest, opts, skip_dirs, include_secrets)

    # 1. 扫描 Codex
    if codex.is_dir():
        C.info(f"扫描 Codex: {codex}", opts.quiet)
        allow = set() if everything else set(CODEX_ROOT_FILES + CODEX_ROOT_DIRS)
        col.collect_root_files(codex, "codex", "codex", allow, max_size)
        manifest["automations"]["codex"] = export_codex_automations(codex)
    else:
        C.warn(f"Codex 目录不存在: {codex}", opts.quiet)

    # 2. 扫描 WorkBuddy
    if wb.is_dir():
        C.info(f"扫描 WorkBuddy: {wb}", opts.quiet)
        allow = set() if everything else set(WORKBUDDY_ROOT_FILES + WORKBUDDY_ROOT_DIRS)
        col.collect_root_files(wb, "workbuddy", "workbuddy", allow, max_size)
        manifest["automations"]["workbuddy"] = export_workbuddy_automations(wb, opts.quiet)
    else:
        C.warn(f"WorkBuddy 目录不存在: {wb}", opts.quiet)

    # 3. 项目索引（workbuddy/projects/ 与 --projects 指定的项目目录）
    #    只保留项目元数据，tool-results 等会话缓存不入包
    PROJECT_RUNTIME = {"tool-results", "sessions", "cache", "tmp", ".tmp", "files"}
    wb_projects = wb / "projects"
    if wb_projects.is_dir():
        for sub in sorted(os.scandir(wb_projects), key=lambda e: e.name):
            sp = Path(sub.path)
            if sub.is_dir():
                col.walk_tree(sp, "workbuddy/projects/" + sp.name, "workbuddy", max_size, extra_skip=PROJECT_RUNTIME)
    # 全局任务记录（tasks/<uuid>/N.json）：与项目会话 uuid 对应，随项目备份携带
    tasks_dir = wb / "tasks"
    if opts.projects and tasks_dir.is_dir():
        col.walk_tree(tasks_dir, "workbuddy/tasks", "workbuddy", max_size, extra_skip=PROJECT_RUNTIME)

    if opts.projects:
        # 项目列表：--projects-dirs 显式指定（可用 auto），否则自动发现存在项目
        if opts.projects_dirs and opts.projects_dirs != ["auto"]:
            proj_dirs = list(opts.projects_dirs)
        else:
            discovered = C.discover_projects(quiet=opts.quiet)
            proj_dirs = [d["path"] for d in discovered if d["exists"]]
            if not opts.quiet:
                C.info(f"自动发现 {len(proj_dirs)} 个使用过的项目文件夹（--list-projects 可预览明细，恢复项目级数据需手动映射路径）", False)
        for proj in proj_dirs:
            p = Path(proj)
            if not p.is_dir():
                C.warn(f"项目目录不存在: {p}，跳过", opts.quiet)
                continue
            # tag：保留中文等安全字符，只替换路径非法字符；重名则加序号
            base_tag = re.sub(r'[<>:"/\\|?*]+', "_", p.name).strip("._") or "project"
            tag = base_tag
            i = 2
            while any(e["relPath"].startswith(f"projects/{tag}/") for e in manifest["entries"]):
                tag = f"{base_tag}-{i}"
                i += 1
            rel = f"projects/{tag}"
            # 项目根规则文件：AGENTS.md / CLAUDE.md（WorkBuddy/Codex 项目级规则）
            for rule in ("AGENTS.md", "CLAUDE.md"):
                rf = p / rule
                if rf.is_file():
                    col.collect_file(rf, rel, "project", max_size)
            # 项目级 .workbuddy/（含 memory/ 每日工作日志）
            pd = p / ".workbuddy"
            if pd.is_dir():
                col.walk_tree(pd, rel, "project", max_size, extra_skip=PROJECT_RUNTIME)
            # 项目对话记录：对应 workbuddy/projects 索引下的会话 jsonl
            idx_dir = wb / "projects" / C.encode_wb_project_dir(p)
            if idx_dir.is_dir():
                for f in sorted(os.scandir(idx_dir), key=lambda e: e.name):
                    fp = Path(f.path)
                    if f.is_file() and fp.name.endswith(".jsonl"):
                        col.collect_file(fp, rel + "/conversations", "project", max_size, allow_jsonl=True)

    # 4. 二次识别：去重
    apply_dedupe(manifest, opts.dedupe, opts.quiet)

    # 5. 统计
    entries = manifest["entries"]
    skills = manifest["skills"]
    total = sum(e["size"] or 0 for e in entries)
    manifest["stats"] = {
        "fileCount": len(entries),
        "totalBytes": total,
        "skillCount": len(skills),
        "codexSkills": sum(1 for s in skills if s["source"] == "codex"),
        "workbuddySkills": sum(1 for s in skills if s["source"] == "workbuddy"),
        "connectorSkills": sum(1 for s in skills if s["source"] == "workbuddy-connector"),
        "codexAutomations": manifest["automations"].get("codex", {}).get("count", 0),
        "workbuddyAutomations": manifest["automations"].get("workbuddy", {}).get("count", 0),
        "excludedCount": len(manifest["excluded"]),
        "sanitizedCount": len(manifest["sanitized"]),
        "suspiciousCount": len(manifest["suspicious"]),
        "secretCount": sum(1 for e in entries if e.get("secret")),
        "entryTypes": {},
    }
    for e in entries:
        manifest["stats"]["entryTypes"][e["type"]] = manifest["stats"]["entryTypes"].get(e["type"], 0) + 1

    # 6. 对比上次备份
    if opts.compare:
        try:
            prev = json.loads(Path(opts.compare).read_text(encoding="utf-8"))
            prev_set = {(e["relPath"], e["sha256"]) for e in prev["entries"]}
            cur_set = {(e["relPath"], e["sha256"]) for e in entries}
            added = [r for r, _ in cur_set - prev_set]
            removed = [r for r, _ in prev_set - cur_set]
            changed = [r for r, h in cur_set if (r, h) not in prev_set and r in {p for p, _ in prev_set}]
            C.info(f"与上次备份对比: 新增 {len(added)}、变更 {len(changed)}、消失 {len(removed)}", opts.quiet)
            for r in sorted(added)[:20]:
                C.info(f"  + {r}", opts.quiet)
            for r in sorted(changed)[:20]:
                C.info(f"  ~ {r}", opts.quiet)
            for r in sorted(removed)[:20]:
                C.info(f"  - {r}", opts.quiet)
        except Exception as e:
            C.warn(f"--compare 失败: {e}", opts.quiet)

    # 7. 写备份包：默认只读；只有显式 --apply 才会创建目录或文件
    if opts.apply:
        archive_mode = opts.zip or opts.to_desktop or include_secrets
        password = resolve_password(opts)
        if include_secrets and not password:
            raise SystemExit("包含敏感配置时必须使用 --password-env、--password-file 或 --prompt-password。")
        if password and not archive_mode:
            raise SystemExit("AES 口令只用于 ZIP；请同时使用 --zip。")
        manifest["options"]["zipEncrypted"] = bool(password)
        preflight_sources(manifest)
        stamp = f"ark-{time.strftime('%Y%m%d-%H%M%S')}"
        if archive_mode:
            if opts.to_desktop:
                zip_path = Path.home() / "Desktop" / f"{stamp}.zip"
            elif opts.out:
                requested = Path(opts.out).expanduser()
                zip_path = requested if requested.suffix.lower() == ".zip" else requested.with_suffix(".zip")
            else:
                zip_path = C.home_dir() / "ark-backups" / f"{stamp}.zip"
            write_zip_backup(zip_path, manifest, password)
            C.info(f"完成：{zip_path}" + ("（AES 加密）" if password else "（未加密，不含敏感配置）"), opts.quiet)
            C.info(f"恢复前先运行：ark_restore.py '{zip_path}' --dry-run", opts.quiet)
        else:
            out_dir = Path(opts.out).expanduser() if opts.out else C.home_dir() / "ark-backups" / stamp
            write_directory_backup(out_dir, manifest)
            C.info(f"完成：{out_dir}", opts.quiet)
            C.info(f"恢复前先运行：ark_restore.py '{out_dir}' --dry-run", opts.quiet)
    else:
        s = manifest["stats"]
        C.info(f"[只读预览] {PROFILE_LABELS[opts.profile]}：{s['fileCount']} 文件 / {C.size_str(s['totalBytes'])}，技能 {s['skillCount']}，敏感配置文件 {s['secretCount']}，排除 {s['excludedCount']}，脱敏 {s['sanitizedCount']}", opts.quiet)
        C.info("[只读预览] 未创建目录、ZIP、报告或清单。确认后单独使用 --apply。", opts.quiet)

    return 0


if __name__ == "__main__":
    sys.exit(main())
