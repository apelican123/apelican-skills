#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方舟验证工具 v3.0：不修改备份包，不自动创建或清理沙箱。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ark_common as C
from ark_restore import BackupReader, validate_manifest


def resolve_password(opts) -> str | None:
    choices = [bool(opts.zip_password), bool(opts.password_file), bool(opts.password_env), bool(opts.prompt_password)]
    if sum(choices) > 1:
        raise SystemExit("口令来源只能选一种")
    if opts.zip_password:
        C.warn("--zip-password 可能进入命令历史；建议使用 --password-env 或隐藏输入。")
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


def stream_sha256(reader: BackupReader, rel: str) -> str:
    digest = hashlib.sha256()
    with reader.open(rel) as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_integrity(reader: BackupReader, manifest: dict, parts: set[str], quiet: bool) -> list[str]:
    failures = []
    checked = 0
    for entry in manifest["entries"]:
        rel = entry["relPath"]
        if PurePosixPath(rel).parts[0] not in parts or entry.get("linkTarget"):
            continue
        if not reader.exists(rel):
            failures.append(f"缺失: {rel}")
            continue
        checked += 1
        expected = entry.get("sha256")
        if expected and stream_sha256(reader, rel) != expected:
            failures.append(f"hash 不一致: {rel}")
    for skill in manifest.get("skills", []):
        rel = skill.get("relPath", "")
        if rel and PurePosixPath(rel).parts[0] in parts and not reader.exists(f"{rel}/SKILL.md"):
            failures.append(f"技能缺少 SKILL.md: {rel}")
    automation = (manifest.get("automations") or {}).get("workbuddy", {})
    if "workbuddy" in parts and automation.get("exported") and not reader.exists("workbuddy/automations.json"):
        failures.append("缺失: workbuddy/automations.json")
    C.info(f"[完整性] 核对 {checked} 个文件", quiet)
    return failures


def run_restore(backup: str, parts: set[str], home: Path, password: str | None,
                apply: bool, quiet: bool) -> tuple[int, str]:
    command = [
        sys.executable, str(Path(__file__).resolve().parent / "ark_restore.py"), backup,
        "--apply" if apply else "--dry-run", "--parts", ",".join(sorted(parts)),
        "--target-home", str(home), "--no-remap-paths",
    ]
    if quiet:
        command.append("--quiet")
    environment = os.environ.copy()
    if password:
        environment["ARK_VERIFY_PASSWORD"] = password
        command += ["--password-env", "ARK_VERIFY_PASSWORD"]
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    detail = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode, detail


def check_sandbox(manifest: dict, parts: set[str], home: Path) -> list[str]:
    failures = []
    for entry in manifest["entries"]:
        rel = entry["relPath"]
        pure = PurePosixPath(rel)
        if pure.parts[0] not in parts or entry.get("linkTarget"):
            continue
        if pure.parts[0] == "projects":
            continue
        target = home / (".codex" if pure.parts[0] == "codex" else ".workbuddy") / Path(*pure.parts[1:])
        if not target.is_file():
            failures.append(f"沙箱恢复缺失: {rel}")
        elif entry.get("sha256") and C.sha256_file(target) != entry["sha256"]:
            failures.append(f"沙箱恢复 hash 不一致: {rel}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="方舟验证：完整性 + 只读恢复预演 + 可选显式沙箱恢复")
    parser.add_argument("backup", help="备份目录或 .zip")
    parser.add_argument("--parts", default="codex,workbuddy")
    parser.add_argument("--sandbox-apply", help="显式提供沙箱用户目录时，执行一次真实恢复；不会自动删除")
    parser.add_argument("--report-dir", help="验证报告目录；默认 ~/.ark/verify-reports")
    parser.add_argument("--no-report", action="store_true", help="不写验证报告")
    parser.add_argument("--zip-password", help="旧版兼容：直接传口令（不推荐）")
    parser.add_argument("--password-file")
    parser.add_argument("--password-env")
    parser.add_argument("--prompt-password", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    opts = parser.parse_args()

    parts = {item.strip() for item in opts.parts.split(",") if item.strip()}
    if not parts <= {"codex", "workbuddy", "projects"}:
        raise SystemExit(f"未知验证范围: {sorted(parts)}")
    password = resolve_password(opts)
    reader = BackupReader(opts.backup, password)
    try:
        manifest = reader.read_json("manifest.json")
        validate_manifest(manifest)
        integrity_failures = check_integrity(reader, manifest, parts, opts.quiet)
    finally:
        reader.close()

    preview_home = Path(opts.sandbox_apply).expanduser().resolve() if opts.sandbox_apply else Path.home() / ".ark" / "nonexistent-preview-target"
    preview_rc, preview_detail = run_restore(opts.backup, parts, preview_home, password, False, opts.quiet)
    failures = list(integrity_failures)
    if preview_rc:
        failures.append(f"只读恢复预演失败（退出码 {preview_rc}）: {preview_detail[-500:]}")

    sandbox_failures = []
    if opts.sandbox_apply:
        sandbox = Path(opts.sandbox_apply).expanduser().resolve()
        sandbox.mkdir(parents=True, exist_ok=True)
        apply_rc, apply_detail = run_restore(opts.backup, parts, sandbox, password, True, opts.quiet)
        if apply_rc:
            sandbox_failures.append(f"沙箱恢复失败（退出码 {apply_rc}）: {apply_detail[-500:]}")
        else:
            sandbox_failures.extend(check_sandbox(manifest, parts, sandbox))
        failures.extend(sandbox_failures)

    report = [
        "# 方舟验证报告", "",
        f"- 备份：`{opts.backup}`",
        f"- 验证时间：{C.utc_now()}",
        f"- 包内完整性：{'通过' if not integrity_failures else '未通过'}",
        f"- 只读恢复预演：{'通过' if preview_rc == 0 else '未通过'}",
        f"- 显式沙箱恢复：{'通过' if opts.sandbox_apply and not sandbox_failures else ('未执行' if not opts.sandbox_apply else '未通过')}",
        "",
    ]
    if failures:
        report += ["## 失败项", *[f"- {item}" for item in failures[:50]], "", "结论：**未通过**，不要作为正式迁移包。"]
    else:
        report += [
            "结论：所选检查通过。它证明包内文件一致且恢复流程可执行；",
            "不证明第三方服务登录态、设备绑定凭据或未来版本客户端会话索引兼容。",
        ]
    if not opts.no_report:
        base = Path(opts.report_dir).expanduser() if opts.report_dir else Path.home() / ".ark" / "verify-reports"
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"verify-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.md"
        path.write_text("\n".join(report), encoding="utf-8")
        C.info(f"报告：{path}", opts.quiet)
    if failures:
        C.warn(f"验证未通过：{failures[:5]}", opts.quiet)
        return 1
    C.info("验证通过：完整性与只读恢复预演均通过。", opts.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
