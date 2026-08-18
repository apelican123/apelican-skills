#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方舟恢复工具 v3.0：默认只读，ZIP 直接流式恢复。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ark_common as C

SUPPORTED_SCHEMAS = {"1.0", "2.0"}
VALID_PARTS = {"codex", "workbuddy", "projects"}
PATH_CONFIG_NAMES = {
    "config.toml", "mcp.json", "settings.json", "models.json",
    "automation.toml", "automations.json", "hooks.json", "keybindings.json",
}


def resolve_password(opts) -> str | None:
    choices = [bool(opts.zip_password), bool(opts.password_file), bool(opts.password_env)]
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
        manifests = [n for n in names if n == "manifest.json" or n.endswith("/manifest.json")]
        if len(manifests) != 1:
            raise SystemExit(f"ZIP 中 manifest.json 数量应为 1，实际为 {len(manifests)}")
        self.prefix = manifests[0][:-len("manifest.json")]

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


def resolve_target(rel: str, home: Path, selected: set[str]) -> tuple[Path, str] | None:
    parts = PurePosixPath(rel).parts
    top = parts[0]
    if top not in selected or top == "projects":
        return None
    base = home / (".codex" if top == "codex" else ".workbuddy")
    target = (base / Path(*parts[1:])).resolve(strict=False)
    try:
        target.relative_to(base.resolve(strict=False))
    except ValueError:
        return None
    return target, top


def detect_fresh(home: Path) -> dict:
    markers = {
        "codex": ["config.toml", "AGENTS.md", "skills", "memories", "automations"],
        "workbuddy": ["SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md", "settings.json", "skills"],
    }
    result = {}
    for name, names in markers.items():
        base = home / (".codex" if name == "codex" else ".workbuddy")
        core = [item for item in names if (base / item).exists()]
        count = sum(1 for p in base.rglob("*") if p.is_file()) if base.is_dir() else 0
        result[name] = {"fresh": not core and count == 0, "coreFiles": core, "fileCount": count}
    return result


def build_plan(manifest: dict, home: Path, selected: set[str]) -> dict:
    plan = {"overwrite": [], "create": [], "skip": [], "extra": [], "links": [], "identity": []}
    wanted = {"codex": set(), "workbuddy": set()}
    for entry in manifest["entries"]:
        rel = entry["relPath"]
        resolved = resolve_target(rel, home, selected)
        if resolved is None:
            plan["skip"].append(rel)
            continue
        target, top = resolved
        if not entry.get("linkTarget"):
            wanted[top].add(rel.split("/", 1)[1])
        if entry.get("linkTarget"):
            plan["links"].append((rel, target, entry["linkTarget"]))
        elif target.exists() and entry.get("sha256") and C.sha256_file(target) == entry["sha256"]:
            plan["skip"].append(rel)
        elif target.exists():
            plan["overwrite"].append((rel, target))
            if entry.get("type") in {"identity", "memory"}:
                plan["identity"].append(rel)
        else:
            plan["create"].append((rel, target))
    for top in selected & {"codex", "workbuddy"}:
        base = home / (".codex" if top == "codex" else ".workbuddy")
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() or path.is_symlink():
                    rel = path.relative_to(base).as_posix()
                    if rel not in wanted[top]:
                        plan["extra"].append(f"{top}/{rel}")
    return plan


def archive_existing(target: Path, root: Path, rel: str) -> bool:
    if not (target.exists() or target.is_symlink()):
        return False
    archive = root / Path(*PurePosixPath(rel).parts)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() or archive.is_symlink():
        raise FileExistsError(f"冲突归档目标已存在: {archive}")
    shutil.move(str(target), str(archive))
    return True


def old_homes(manifest: dict) -> list[str]:
    values = []
    for source in (manifest.get("sources") or {}).values():
        raw = source.get("home") if isinstance(source, dict) else None
        if raw:
            path = Path(raw)
            home = str(path.parent) if path.name.lower() in {".codex", ".workbuddy"} else str(path)
            if home not in values:
                values.append(home)
    return values


def remap_paths(path: Path, manifest: dict, home: Path) -> bool:
    if path.name not in PATH_CONFIG_NAMES:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    original = text
    new = str(home)
    for old in sorted(old_homes(manifest), key=len, reverse=True):
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


def safe_link(target: Path, link_target: str, base: Path) -> bool:
    raw = Path(link_target)
    if raw.is_absolute():
        return False
    resolved = (target.parent / raw).resolve(strict=False)
    try:
        resolved.relative_to(base.resolve(strict=False))
        return True
    except ValueError:
        return False


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
    lines += ["## 结论", "", "源文件写入后已先按 manifest 校验；路径适配会使最终 hash 变化，这是预期结果。",
              "账号登录文件、Cookie、系统钥匙串和 OAuth 授权不在恢复范围内；请按新设备流程重新登录。"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="方舟恢复：默认只读预览，显式 --apply 才写入")
    parser.add_argument("backup", help="备份目录或 .zip")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只输出计划，不写目标/备份目录（默认）")
    mode.add_argument("--apply", action="store_true", help="执行恢复；覆盖前始终归档旧文件")
    parser.add_argument("--parts", default="codex,workbuddy", help="范围：codex,workbuddy；projects 只列出")
    parser.add_argument("--target-home", help="目标用户主目录；默认当前用户")
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
    if "projects" in selected:
        C.warn("projects 只列出；本次不会自动写项目目录。", opts.quiet)
    home = Path(opts.target_home).expanduser().resolve() if opts.target_home else Path.home().resolve()
    reader = BackupReader(opts.backup, resolve_password(opts))
    try:
        manifest = reader.read_json("manifest.json")
        validate_manifest(manifest)
        fresh = detect_fresh(home)
        if opts.fresh:
            occupied = [part for part in selected & {"codex", "workbuddy"} if not fresh[part]["fresh"]]
            if occupied:
                raise SystemExit(f"--fresh 断言失败，目标已有内容: {occupied}；未写入。")
        plan = build_plan(manifest, home, selected - {"projects"})
        C.info(f"计划：覆盖 {len(plan['overwrite'])}，新增 {len(plan['create'])}，已一致 {len(plan['skip'])}，本地多出 {len(plan['extra'])}", opts.quiet)
        if plan["identity"]:
            C.warn("将覆盖身份/记忆文件；执行时旧版会先归档：" + "、".join(plan["identity"][:12]), opts.quiet)
        if not opts.apply:
            for rel, target in sorted(plan["overwrite"])[:50]:
                C.info(f"  [覆盖] {rel} -> {target}", opts.quiet)
            for rel, target in sorted(plan["create"])[:50]:
                C.info(f"  [新增] {rel} -> {target}", opts.quiet)
            C.info("只读预览完成：目标目录与备份包均未写入。确认后单独使用 --apply。", opts.quiet)
            return 0

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        conflict_root = home / ".ark" / "restore-conflicts" / stamp
        report_root = home / ".ark" / "restore-reports" / stamp
        conflict_root.mkdir(parents=True, exist_ok=False)
        report_root.mkdir(parents=True, exist_ok=False)
        errors: list[str] = []
        failed: list[str] = []
        remapped: list[str] = []
        entry_map = {entry["relPath"]: entry for entry in manifest["entries"]}
        for rel, target in plan["overwrite"] + plan["create"]:
            try:
                if not reader.exists(rel):
                    errors.append(f"备份内缺失: {rel}")
                    continue
                archive_existing(target, conflict_root, rel)
                reader.copy_to(rel, target)
                expected = entry_map[rel].get("sha256")
                if expected and C.sha256_file(target) != expected:
                    failed.append(rel)
            except OSError as exc:
                errors.append(f"{rel}: {exc}")
        for rel, target, link_target in plan["links"]:
            top = rel.split("/", 1)[0]
            base = home / (".codex" if top == "codex" else ".workbuddy")
            try:
                if not safe_link(target, link_target, base):
                    errors.append(f"拒绝跨根软链接: {rel} -> {link_target}")
                    continue
                archive_existing(target, conflict_root, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(link_target)
            except OSError as exc:
                errors.append(f"软链接 {rel}: {exc}")
        if not opts.no_remap_paths:
            for rel, target in plan["overwrite"] + plan["create"]:
                if target.is_file() and remap_paths(target, manifest, home):
                    remapped.append(rel)
        auto_plan = automation_plan(reader, report_root, manifest, home)
        report = render_report(manifest, plan, str(reader.path), conflict_root, errors, failed, remapped, auto_plan)
        report_path = report_root / "restore-report.md"
        report_path.write_text(report, encoding="utf-8")
        C.info(f"恢复完成：错误 {len(errors)}，hash 失败 {len(failed)}，路径适配 {len(remapped)}；报告 {report_path}", opts.quiet)
        return 0 if not errors and not failed else 1
    finally:
        reader.close()


if __name__ == "__main__":
    sys.exit(main())
