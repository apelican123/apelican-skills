#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方舟公开包只读自检：检查运行时、脚本完整性与可选 AES 依赖。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


MIN_PYTHON = (3, 10)
CORE_SCRIPTS = ("ark_common.py", "ark_backup.py", "ark_restore.py", "ark_verify.py", "ark_selfcheck.py")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="方舟公开包只读自检")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    package_root = script_dir.parent
    checksums_path = package_root / "references" / "checksums.json"
    python_ok = sys.version_info >= MIN_PYTHON
    missing = [name for name in CORE_SCRIPTS if not (script_dir / name).is_file()]
    compile_failures: list[str] = []
    for name in CORE_SCRIPTS:
        path = script_dir / name
        if not path.is_file():
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, UnicodeError, SyntaxError) as error:
            compile_failures.append(f"{name}: {error}")

    checksum_failures: list[str] = []
    checksum_status = "未提供"
    if checksums_path.is_file():
        checksum_status = "通过"
        try:
            expected = json.loads(checksums_path.read_text(encoding="utf-8"))
            for rel, wanted in expected.get("sha256", {}).items():
                target = package_root / Path(rel)
                if not target.is_file():
                    checksum_failures.append(f"缺少 {rel}")
                elif sha256(target) != wanted:
                    checksum_failures.append(f"hash 不一致 {rel}")
        except (OSError, ValueError, TypeError) as error:
            checksum_failures.append(f"无法读取 checksums.json: {error}")
        if checksum_failures:
            checksum_status = "失败"

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    workbuddy_home = Path(os.environ.get("WORKBUDDY_HOME", Path.home() / ".workbuddy")).expanduser()
    pyzipper_ok = importlib.util.find_spec("pyzipper") is not None
    core_ok = python_ok and not missing and not compile_failures and not checksum_failures
    result = {
        "package": "apelican-ark",
        "python": {"version": sys.version.split()[0], "minimum": "3.10", "ok": python_ok},
        "scripts": {"missing": missing, "compileFailures": compile_failures},
        "checksums": {"status": checksum_status, "failures": checksum_failures},
        "homes": {
            "codex": {"path": str(codex_home), "exists": codex_home.is_dir()},
            "workbuddy": {"path": str(workbuddy_home), "exists": workbuddy_home.is_dir()},
        },
        "features": {
            "basicBackupReady": core_ok,
            "aesSensitiveConfigReady": core_ok and pyzipper_ok,
            "pyzipperInstalled": pyzipper_ok,
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[方舟] Python {result['python']['version']}：{'通过' if python_ok else '需要 3.10+'}")
        print(f"[方舟] 核心脚本：{'通过' if not missing and not compile_failures else '失败'}")
        print(f"[方舟] 文件校验：{checksum_status}")
        print(f"[方舟] Codex：{'已发现' if codex_home.is_dir() else '未发现'}（{codex_home}）")
        print(f"[方舟] WorkBuddy：{'已发现' if workbuddy_home.is_dir() else '未发现'}（{workbuddy_home}）")
        print(f"[方舟] 基础备份：{'可用' if core_ok else '不可用'}")
        print(f"[方舟] AES 敏感配置包：{'可用' if core_ok and pyzipper_ok else '需安装 pyzipper' if core_ok else '不可用'}")
        if missing:
            print("[方舟] 缺少文件：" + ", ".join(missing))
        for failure in compile_failures + checksum_failures:
            print("[方舟] " + failure)

    return 0 if core_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
