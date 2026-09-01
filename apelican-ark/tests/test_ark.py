#!/usr/bin/env python3
"""方舟 v3.2 离线回归；只使用生成的假数据，成功后默认清理临时目录。"""

from __future__ import annotations

import hashlib
import gc
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

import pyzipper
from pathlib import Path


ROOT = Path(os.environ.get("ARK_TEST_SKILL_ROOT", Path(__file__).resolve().parents[1])).resolve()
BACKUP = ROOT / "scripts" / "ark_backup.py"
RESTORE = ROOT / "scripts" / "ark_restore.py"
VERIFY = ROOT / "scripts" / "ark_verify.py"


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def run(args: list[str], env: dict[str, str], expected: int = 0) -> subprocess.CompletedProcess:
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env)
    if result.returncode != expected:
        raise AssertionError(
            f"expected {expected}, got {result.returncode}\nCMD={args}\nOUT={result.stdout}\nERR={result.stderr}"
        )
    return result


def tree_hashes(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def make_dir_link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        script = "& { param($linkPath,$targetPath) New-Item -ItemType Junction -Path $linkPath -Target $targetPath | Out-Null }"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script, str(link), str(target)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr or result.stdout)
    else:
        link.symlink_to(target, target_is_directory=True)


def remove_fixture_safely(root: Path) -> None:
    """Remove Windows junctions before rmtree so cleanup never follows them."""
    reparse = 0x400
    for dirpath, dirnames, _files in os.walk(root, topdown=True):
        keep = []
        for name in dirnames:
            path = Path(dirpath) / name
            try:
                attrs = getattr(path.lstat(), "st_file_attributes", 0)
                if attrs & reparse:
                    path.rmdir()
                    continue
            except OSError:
                pass
            keep.append(name)
        dirnames[:] = keep
    if os.name == "nt":
        import ctypes
        for dirpath, dirnames, filenames in os.walk(root, topdown=False):
            for name in [*filenames, *dirnames]:
                ctypes.windll.kernel32.SetFileAttributesW(str(Path(dirpath) / name), 0x80)
        ctypes.windll.kernel32.SetFileAttributesW(str(root), 0x80)
    shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    fixture = Path(tempfile.mkdtemp(prefix="ark-v3-regression-"))
    source_home = fixture / "source-user"
    codex = source_home / ".codex"
    workbuddy = source_home / ".workbuddy"
    hermes = source_home / "hermes-home"
    memory_tencentdb = source_home / ".memory-tencentdb"
    gateway_source = source_home / "MemoryCore" / "src" / "gateway" / "server.ts"
    gateway_config = source_home / "MemoryCore" / "tdai-gateway.standalone.yaml"
    write(codex / "AGENTS.md", "# fixture\n")
    portable_key = "sk-" + "A" * 30
    write(codex / "config.toml", f'tool_path = "{source_home}\\tools"\napi_key = "{portable_key}"\n')
    leaked_line_secret = "sk-" + "L" * 32
    write(codex / "config.local.json", f"free text before secret {leaked_line_secret} after secret\n")
    write(codex / "auth.json", '{"token":"fixture-portable-token"}\n')
    write(codex / ".credentials.json", '{"token":"fixture-account-state"}\n')
    write(codex / "cookies" / "session.json", '{"cookie":"fixture-cookie"}\n')
    write(codex / "skills" / "fixture-skill" / "SKILL.md", "---\nname: fixture-skill\ndescription: fixture\n---\n")
    write(codex / "skills" / "fixture-skill" / "manifest.json", '{"name":"nested-skill-manifest"}\n')
    write(codex / "skills" / "fixture-skill" / "__pycache__" / "module.pyc", "volatile-bytecode\n")
    large_secret = "sk-" + "Z" * 40
    write(codex / "skills" / "fixture-skill" / "large-secret.txt",
          "x" * (4 * 1024 * 1024) + "\n" + large_secret + "\n")
    array_secret = "sk-" + "Q" * 40
    write(codex / "skills" / "fixture-skill" / "array-secret.json",
          json.dumps({"tokens": [array_secret]}))
    write(workbuddy / "SOUL.md", "fixture soul\n")
    write(workbuddy / "IDENTITY.md", "fixture identity\n")
    write(workbuddy / "USER.md", "fixture user\n")
    write(workbuddy / "MEMORY.md", "fixture memory\n")
    write(workbuddy / "settings.json", json.dumps({"workspace": str(source_home / "project")}))
    write(workbuddy / "mcp.json", json.dumps({"headers": {"Authorization": "Bearer fixture-portable-token"}}))
    write(workbuddy / "credentials" / "account.json", '{"token":"fixture-account-state"}\n')
    database = workbuddy / "workbuddy.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE automations (id TEXT, name TEXT, prompt TEXT, cwds TEXT, deleted_at TEXT, owner_user_id TEXT, owner_status TEXT, owner_source TEXT, updated_at TEXT)"
        )
        connection.execute(
            "INSERT INTO automations VALUES ('a1','fixture','do fixture',?,NULL,NULL,NULL,NULL,NULL)",
            (json.dumps([str(source_home / "project")]),),
        )

    write(hermes / "config.yaml", "memory:\n  provider: memory_tencentdb\n")
    write(hermes / "SOUL.md", "fixture hermes soul\n")
    write(hermes / "auth.json", '{"providers":{"openai-codex":{"tokens":{"access_token":"fixture-hermes-access","refresh_token":"fixture-hermes-refresh"}}}}\n')
    write(hermes / "shared" / "nous_auth.json", '{"access_token":"fixture-nous-access","refresh_token":"fixture-nous-refresh"}\n')
    write(hermes / "skills" / "hermes-fixture" / "SKILL.md", "---\nname: hermes-fixture\ndescription: fixture\n---\n")
    write(hermes / "memories" / "MEMORY.md", "fixture hermes memory\n")
    write(hermes / "kanban" / ".dispatcher.lock", "volatile process lock\n")
    write(gateway_source, "// source-only gateway fixture\n")
    write(
        gateway_config,
        f'data:\n  baseDir: "{memory_tencentdb / "memory-tdai"}"\n'
        'llm:\n  apiKey: "fixture-gateway-secret"\n',
    )
    write(
        hermes / ".env",
        f'MEMORY_TENCENTDB_GATEWAY_CMD="node --import tsx {gateway_source.as_posix()}"\n'
        f'TDAI_GATEWAY_CONFIG="{gateway_config.as_posix()}"\n'
        'MEMORY_TENCENTDB_LLM_API_KEY="fixture-hermes-secret"\n',
    )
    vector_db = memory_tencentdb / "memory-tdai" / "vectors.db"
    vector_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(vector_db) as connection:
        connection.execute("CREATE TABLE memories (id TEXT, value TEXT)")
        connection.execute("INSERT INTO memories VALUES ('m1', 'fixture vector memory')")
    write(memory_tencentdb / "memory-tdai" / "records" / "2026-08-20.jsonl", '{"fixture":true}\n')
    write(
        memory_tencentdb / "memory-tdai" / "instances" / "default"
        / "memory-generation-logs" / "v1" / "volatile.json",
        '{"prompt":{},"input_refs":[],"output_refs":[],"status":"succeeded"}\n',
    )
    runtime = memory_tencentdb / "tdownload" / "node_modules"
    write(runtime / "tsx" / "dist" / "loader.mjs", "// fixture loader\n")
    write(
        runtime / "@tencentdb-agent-memory" / "memory-tencentdb" / "src" / "gateway" / "server.ts",
        "// fixture portable gateway\n",
    )
    write(memory_tencentdb / "tdownload" / "package.json", '{"name":"tdownload"}\n')

    # Complete-mode fixture: every Hermes user artifact class, a named profile,
    # cron/project closure, external source topology, desktop ctx.storage, and
    # an untracked custom memory provider source.
    agents_skills = source_home / ".agents" / "skills"
    write(agents_skills / "external-skill" / "SKILL.md", "---\nname: external-skill\ndescription: external\n---\n")
    external_evolved = source_home / "external-evolved"
    write(external_evolved / "evolved" / "SKILL.md", "---\nname: evolved\ndescription: evolved\n---\n")
    make_dir_link(agents_skills / "evolved-skills", external_evolved)
    make_dir_link(hermes / "skills" / "external-link", agents_skills / "external-skill")
    write(hermes / "profile.yaml", "display_name: Fixture\n")
    write(hermes / "scripts" / "daily.py", "print('fixture cron')\n")
    external_cron_script = source_home / "external-cron" / "notify.py"
    write(external_cron_script, "print('external fixture cron')\n")
    write(hermes / "assets" / "badge.txt", "fixture asset\n")
    write(hermes / "tui-widgets" / "fixture" / "widget.py", "# fixture widget\n")
    write(hermes / "webhooks" / "fixture.json", '{"enabled":true}\n')
    write(hermes / "plugin-data" / "fixture-plugin" / "state.json", '{"count":2}\n')
    write(hermes / "desktop-plugins" / "fixture" / "plugin.js", "export default {id:'fixture',register(){}}\n")
    write(hermes / "plugins" / "unified" / "plugin.yaml", "name: unified\n")
    write(hermes / "plugins" / "unified" / "desktop" / "plugin.js", "export default {id:'unified',register(){}}\n")
    provider_repo = hermes / "hermes-agent"
    provider_rel = Path("plugins") / "memory" / "memory_tencentdb"
    write(provider_repo / provider_rel / "plugin.yaml",
          "name: memory_tencentdb\nkind: memory-provider\n")
    write(provider_repo / provider_rel / "provider.py", "# fixture tracked provider source\n")
    subprocess.run(["git", "-C", str(provider_repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(provider_repo), "config", "user.email", "ark@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(provider_repo), "config", "user.name", "Ark Test"], check=True)
    subprocess.run(["git", "-C", str(provider_repo), "add", provider_rel.as_posix()], check=True)
    subprocess.run(["git", "-C", str(provider_repo), "commit", "-m", "provider fixture"], check=True,
                   capture_output=True)
    write(provider_repo / provider_rel / "provider.py", "# fixture dirty provider source\n")
    profile = hermes / "profiles" / "researcher"
    write(profile / "profile.yaml", "description: Fixture researcher\n")
    write(profile / "config.yaml", "memory:\n  provider: built-in\n")
    write(profile / "auth.json", '{"providers":{"openai-codex":{"tokens":{"refresh_token":"fixture-profile-refresh"}}}}\n')
    write(profile / "SOUL.md", "fixture researcher soul\n")
    write(profile / "skills" / "profile-skill" / "SKILL.md", "---\nname: profile-skill\ndescription: profile\n---\n")
    write(profile / "memories" / "MEMORY.md", "profile memory\n")
    write(profile / "state-snapshots" / "pre-update" / "state.db", "derived snapshot\n")
    write(hermes / "gateway.heartbeat", "volatile-live-heartbeat\n")
    write(hermes / "state" / "gateway.heartbeat", "volatile-nested-heartbeat\n")
    write(hermes / "skills" / ".usage.json", '{"volatile":true}\n')

    project = source_home / "project"
    write(project / "AGENTS.md", "# project instructions\n")
    write(project / "src" / "main.py", "print('project')\n")
    write(project / ".git" / "HEAD", "ref: refs/heads/main\n")
    write(project / "logs" / "audit.log", "user-owned project log\n")
    write(project / "dist" / "release.txt", "user-owned release artifact\n")
    project_db = project / "data" / "project.db"
    project_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(project_db) as connection:
        connection.execute("CREATE TABLE data (value TEXT)")
        connection.execute("INSERT INTO data VALUES ('portable project data')")
    projects_db = hermes / "projects.db"
    with sqlite3.connect(projects_db) as connection:
        connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, slug TEXT, name TEXT, description TEXT, icon TEXT, color TEXT, board_slug TEXT, primary_path TEXT, created_at TEXT, archived INTEGER)")
        connection.execute("CREATE TABLE project_folders (project_id TEXT, path TEXT, label TEXT, is_primary INTEGER, added_at TEXT)")
        connection.execute("INSERT INTO projects VALUES ('p1','fixture','Fixture Project','','','','',?, '',0)", (str(project),))
        connection.execute("INSERT INTO project_folders VALUES ('p1',?,'fixture',1,'')", (str(project),))
    write(hermes / "cron" / "jobs.json", json.dumps({"jobs": [{
        "id": "job1", "name": "fixture cron", "skills": ["external-skill"],
        "script": "daily.py", "workdir": str(project), "no_agent": True,
        "schedule": {"kind": "cron", "expr": "0 1 * * *"}, "enabled": True,
    }, {
        "id": "job2", "name": "external script cron", "skills": [],
        "script": str(external_cron_script), "workdir": str(project), "no_agent": True,
        "schedule": {"kind": "cron", "expr": "15 1 * * *"}, "enabled": True,
    }]}, ensure_ascii=False))
    local_mcp = source_home / "AppData" / "Local" / "fixture-readonly-mcp"
    runtime_command = local_mcp / ".runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    write(
        local_mcp / "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'backend'\nbackend-path = ['scripts']\n\n"
        "[project]\nname = 'fixture-readonly-mcp'\nversion = '0.1.0'\nrequires-python = '>=3.11,<4'\n",
    )
    write(local_mcp / "requirements.in", "# zero external dependencies\n")
    write(
        local_mcp / "requirements.lock",
        "# This file was autogenerated by uv via the following command:\n"
        "#    uv pip compile requirements.in --generate-hashes -o requirements.lock\n",
    )
    write(local_mcp / "README.md", "# fixture local stdio MCP\n")
    write(local_mcp / "SPEC.md", "read-only fixture\n")
    write(local_mcp / "AGENTS.md", "# fixture rules\n")
    write(local_mcp / "run-server.cmd", "@echo off\n")
    write(local_mcp / "scripts" / "probe_mcp.py", "print('probe')\n")
    write(
        local_mcp / "scripts" / "backend.py",
        "from pathlib import Path\nimport csv, hashlib, base64, zipfile\n"
        "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n"
        "    name='fixture_readonly_mcp-0.1.0-py3-none-any.whl'\n"
        "    out=Path(wheel_directory)/name\n"
        "    files={}\n"
        "    root=Path(__file__).resolve().parents[1]\n"
        "    for p in (root/'src'/'fixture_readonly_mcp').glob('*.py'):\n"
        "        files['fixture_readonly_mcp/'+p.name]=p.read_bytes()\n"
        "    dist='fixture_readonly_mcp-0.1.0.dist-info/'\n"
        "    files[dist+'METADATA']=b'Metadata-Version: 2.1\\nName: fixture-readonly-mcp\\nVersion: 0.1.0\\n'\n"
        "    files[dist+'WHEEL']=b'Wheel-Version: 1.0\\nGenerator: ark-test\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n'\n"
        "    rows=[]\n"
        "    for n,b in files.items():\n"
        "        d=base64.urlsafe_b64encode(hashlib.sha256(b).digest()).rstrip(b'=')\n"
        "        rows.append((n,'sha256='+d.decode(),str(len(b))))\n"
        "    record=dist+'RECORD'; rows.append((record,'',''))\n"
        "    import io; s=io.StringIO(); csv.writer(s,lineterminator='\\n').writerows(rows); files[record]=s.getvalue().encode()\n"
        "    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:\n"
        "        for n,b in files.items(): z.writestr(n,b)\n"
        "    return name\n",
    )
    write(local_mcp / "src" / "fixture_readonly_mcp" / "__init__.py", "__version__ = '0.1.0'\n")
    write(local_mcp / "src" / "fixture_readonly_mcp" / "server.py", "READ_ONLY = True\n")
    write(local_mcp / "tests" / "test_server.py", "def test_read_only(): assert True\n")
    write(local_mcp / "state" / "managed-playlists.json", '{"playlists":[]}\n')
    write(local_mcp / "state" / ".applemusic-mcp" / "Chrome" / "Cookies", "never-copy-cookie\n")
    write(local_mcp / "state" / "confirmations" / "pending.json", '{"write":true}\n')
    write(local_mcp / "state" / "token.json", '{"token":"never-copy"}\n')
    write(local_mcp / "credentials" / "locker.json", '{"secret":"never-copy"}\n')
    write(local_mcp / ".runtime" / "Scripts" / "python.exe", "never-copy-runtime\n")
    write(local_mcp / ".venv-test" / "marker", "never-copy-venv\n")
    write(local_mcp / "build" / "artifact.whl", "never-copy-build\n")
    write(local_mcp / ".git" / "config", "never-copy-git\n")
    node_mcp = source_home / "AppData" / "Local" / "fixture-node-mcp-root"
    node_package = "is-number"
    node_entry = node_mcp / "node_modules" / node_package / "index.js"
    write(
        node_mcp / "package.json",
        json.dumps({
            "name": "fixture-node-mcp-root", "version": "1.0.0", "private": True,
            "dependencies": {node_package: "7.0.0"},
        }, ensure_ascii=False, indent=2) + "\n",
    )
    write(
        node_mcp / "package-lock.json",
        json.dumps({
            "name": "fixture-node-mcp-root", "version": "1.0.0",
            "lockfileVersion": 3, "requires": True,
            "packages": {
                "": {
                    "name": "fixture-node-mcp-root", "version": "1.0.0",
                    "dependencies": {node_package: "7.0.0"},
                },
                f"node_modules/{node_package}": {
                    "version": "7.0.0",
                    "resolved": "https://registry.npmjs.org/is-number/-/is-number-7.0.0.tgz",
                    "integrity": "sha512-41Cifkg6e8TylSpdtTpeLVMqvSBEVzTttHvERD741+pnZ8ANv0004MRL43QKPDlK9cGvNp6NZWZUBlbGXYxxng==",
                },
            },
        }, ensure_ascii=False, indent=2) + "\n",
    )
    write(
        node_mcp / "src" / node_package / "package.json",
        json.dumps({"name": node_package, "version": "7.0.0", "main": "index.js"}) + "\n",
    )
    write(node_mcp / "src" / node_package / "index.js", "module.exports = { readOnly: true };\n")
    write(node_entry, "module.exports = { sourceRuntimeMustNotBeCopied: true };\n")
    write(node_mcp / "credentials" / "device-auth.json", '{"token":"never-copy-node-auth"}\n')
    write(
        hermes / "config.yaml",
        "memory:\n  provider: memory_tencentdb\n"
        "skills:\n  external_dirs:\n"
        f"    - \"{(agents_skills / 'external-skill').as_posix()}\"\n"
        "mcp_servers:\n  fixture-local-managed:\n"
        f"    command: \"{runtime_command.as_posix()}\"\n"
        "    args:\n      - -m\n      - fixture_readonly_mcp.server\n"
        f"    env:\n      APPLEMUSIC_MCP_HOME: \"{(local_mcp / 'state').as_posix()}\"\n"
        "  fixture-node-local:\n"
        "    command: node\n"
        f"    args:\n      - \"{node_entry.as_posix()}\"\n",
    )
    researcher_mcp = source_home / "AppData" / "Local" / "researcher-readonly-mcp"
    shutil.copytree(local_mcp, researcher_mcp)
    researcher_runtime = researcher_mcp / ".runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    write(
        profile / "config.yaml",
        "memory:\n  provider: built-in\n"
        "mcp_servers:\n  researcher-local:\n"
        f"    command: \"{researcher_runtime.as_posix()}\"\n"
        "    args:\n      - -m\n      - fixture_readonly_mcp.server\n"
        f"    env:\n      FIXTURE_MCP_HOME: \"{(researcher_mcp / 'state').as_posix()}\"\n",
    )
    desktop = source_home / "AppData" / "Roaming" / "Hermes"
    write(desktop / "Local Storage" / "leveldb" / "000003.ldb", "hermes.plugin.fixture.lastTab=board\nprompt-snippets=fixture\n")
    write(desktop / "Local Storage" / "leveldb" / "CURRENT", "MANIFEST-000001\n")
    write(desktop / "Local Storage" / "leveldb" / "LOCK", "")
    write(desktop / "window-state.json", '{"width":1200,"height":800}\n')
    write(desktop / "native-theme.json", '{"theme":"dark"}\n')
    write(desktop / "Network" / "Cookies", "never-copy-cookie\n")
    write(desktop / "connection.json", '{"token":"never-copy-connection"}\n')
    write(memory_tencentdb / "memory-tdai" / "L0" / "scene.json", '{"scene":"fixture"}\n')
    write(memory_tencentdb / "memory-tdai" / "L1" / "persona.json", '{"persona":"fixture"}\n')
    write(memory_tencentdb / "memory-tdai" / "L2" / "memory.json", '{"memory":"fixture"}\n')
    write(memory_tencentdb / "memory-tdai" / "L3" / "conversation.jsonl", '{"conversation":"fixture"}\n')
    write(source_home / ".config" / "himalaya" / "config.toml", "default-account = 'qq'\n")
    write(source_home / ".config" / "himalaya" / "secrets" / "qq.pass", "fixture-mail-authorization-code\n")
    write(source_home / ".yescan" / "config.json", '{"SCAN_WEBSERVICE_KEY":"fixture-yescan-key"}\n')
    write(source_home / ".opencli" / "settings.json", '{"bridge":"chrome"}\n')
    write(source_home / ".workbuddy-key-fallback" / ".env", "FALLBACK_API_KEY=fixture-fallback-key\n")
    write(source_home / ".local" / "share" / "opencode" / "auth.json",
          '{"opencode-go":{"type":"api","key":"fixture-opencode-key"}}\n')

    env = os.environ.copy()
    env["HOME"] = str(source_home)
    env["USERPROFILE"] = str(source_home)
    env["APPDATA"] = str(source_home / "AppData" / "Roaming")
    env["LOCALAPPDATA"] = str(source_home / "AppData" / "Local")
    env["CODEX_HOME"] = str(codex)
    env["WORKBUDDY_HOME"] = str(workbuddy)
    env["HERMES_HOME"] = str(hermes)
    env["MEMORY_TENCENTDB_ROOT"] = str(memory_tencentdb)
    ambient_gateway = source_home / "ambient-gateway.yaml"
    write(ambient_gateway, "data:\n  baseDir: ambient\n")
    env["TDAI_GATEWAY_CONFIG"] = str(ambient_gateway)
    env["FIXTURE_MCP_TOKEN"] = "fixture-process-env-secret"
    env["ARK_SKIP_SOFTWARE_PROBES"] = "1"
    env["npm_config_cache"] = str(fixture / "npm-cache")

    credential_no_password = fixture / "credential-no-password.zip"
    run([str(BACKUP), "--profile", "credentials", "--out", str(credential_no_password), "--apply"],
        env, expected=1)
    assert not credential_no_password.exists()

    credential_zip = fixture / "ark-credentials.zip"
    env["ARK_CREDENTIAL_PASSWORD"] = "fixture-credential-password"
    run([str(BACKUP), "--profile", "credentials", "--password-env", "ARK_CREDENTIAL_PASSWORD",
         "--out", str(credential_zip), "--apply"], env)
    assert credential_zip.is_file()
    with zipfile.ZipFile(credential_zip) as ordinary:
        names = ordinary.namelist()
        assert not any(name.startswith("hermes/memories/") for name in names)
        assert not any(name.startswith("hermes-memory/.memory-tencentdb/memory-tdai/") for name in names)
        assert not any(name.startswith("codex/sessions/") for name in names)
    with pyzipper.AESZipFile(credential_zip) as encrypted_archive:
        encrypted_archive.setpassword(env["ARK_CREDENTIAL_PASSWORD"].encode("utf-8"))
        credential_manifest = json.loads(encrypted_archive.read("manifest.json"))
    assert credential_manifest["options"]["profile"] == "credentials"
    assert credential_manifest["options"]["includePortableOAuth"] is True
    assert len(credential_manifest["portableAuth"]) >= 5

    credential_target = fixture / "credential-target"
    run([str(RESTORE), str(credential_zip), "--apply", "--password-env", "ARK_CREDENTIAL_PASSWORD",
         "--target-home", str(credential_target)], env)
    credential_hermes = ((credential_target / "AppData" / "Local" / "hermes")
                         if os.name == "nt" else credential_target / ".hermes")
    assert (credential_target / ".codex" / "auth.json").is_file()
    assert (credential_hermes / "auth.json").is_file()
    assert (credential_hermes / "shared" / "nous_auth.json").is_file()
    assert (credential_hermes / "profiles" / "researcher" / "auth.json").is_file()
    assert (credential_target / ".local" / "share" / "opencode" / "auth.json").is_file()
    assert (credential_target / ".config" / "himalaya" / "secrets" / "qq.pass").is_file()
    assert (credential_hermes / ".env").is_file()
    assert not (credential_hermes / "memories").exists()

    credential_preserve_target = fixture / "credential-preserve-target"
    write(credential_preserve_target / ".codex" / "auth.json", "newer-target-auth\n")
    run([str(RESTORE), str(credential_zip), "--apply", "--password-env", "ARK_CREDENTIAL_PASSWORD",
         "--target-home", str(credential_preserve_target)], env)
    assert (credential_preserve_target / ".codex" / "auth.json").read_text(encoding="utf-8") == "newer-target-auth\n"
    run([str(VERIFY), str(credential_zip), "--password-env", "ARK_CREDENTIAL_PASSWORD", "--no-report"], env)

    dry_output = fixture / "must-not-exist"
    run([str(BACKUP), "--profile", "basic", "--out", str(dry_output)], env)
    assert not dry_output.exists(), "默认备份预览发生写入"

    both_output = fixture / "both-must-not-exist"
    run([str(BACKUP), "--dry-run", "--apply", "--out", str(both_output)], env, expected=2)
    assert not both_output.exists(), "互斥参数失败后仍写入"

    backup_dir = fixture / "backup-basic"
    run([str(BACKUP), "--profile", "basic", "--out", str(backup_dir), "--apply"], env)
    assert (backup_dir / "manifest.json").is_file()
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "2.2"
    assert manifest["options"]["profileLabel"].startswith("基础备份")
    assert "sk-" not in (backup_dir / "codex" / "config.toml").read_text(encoding="utf-8")
    assert not (backup_dir / "codex" / "skills" / "fixture-skill" / "large-secret.txt").exists()
    array_redacted = (backup_dir / "codex" / "skills" / "fixture-skill" / "array-secret.json").read_text(encoding="utf-8")
    assert array_secret not in array_redacted and "${REDACTED_VALUE}" in array_redacted
    redacted_free_text = (backup_dir / "codex" / "config.local.json").read_text(encoding="utf-8")
    assert leaked_line_secret not in redacted_free_text and "free text before secret" not in redacted_free_text
    assert (backup_dir / "hermes" / "config.yaml").is_file()

    assert "provider: memory_tencentdb" in (backup_dir / "hermes" / "config.yaml").read_text(encoding="utf-8")
    assert not (backup_dir / "hermes" / ".env").exists()
    assert (backup_dir / "hermes-memory" / ".memory-tencentdb" / "memory-tdai" / "vectors.db").is_file()
    assert not (backup_dir / "hermes-memory" / ".memory-tencentdb" / "memory-tdai"
                / "instances" / "default" / "memory-generation-logs").exists()
    assert any(item["reason"] == "derived-memory-generation-audit-log"
               and item["originPath"].endswith("memory-generation-logs")
               for item in manifest["excluded"])
    assert not (backup_dir / "hermes-memory" / ".memory-tencentdb" / "tdownload").exists()
    restored_yaml = backup_dir / "hermes-memory" / ".memory-tencentdb" / "tdai-gateway.standalone.yaml"
    assert restored_yaml.is_file() and "fixture-gateway-secret" not in restored_yaml.read_text(encoding="utf-8")
    assert "baseDir: ambient" not in restored_yaml.read_text(encoding="utf-8")
    assert manifest["stats"]["hermesSkills"] >= 2
    for generated in ("SOFTWARE.md", "CONFIGURATION.md", "INSTALLATION.md", "REAUTHORIZE.md"):
        assert (backup_dir / generated).is_file()

    before = tree_hashes(backup_dir)
    target = fixture / "target-user"
    run([str(RESTORE), str(backup_dir), "--dry-run", "--target-home", str(target)], env)
    assert not target.exists(), "restore dry-run 创建了目标目录"
    assert tree_hashes(backup_dir) == before, "restore dry-run 修改了备份包"
    run([str(RESTORE), str(backup_dir), "--dry-run", "--apply", "--target-home", str(target)], env, expected=2)
    assert not target.exists(), "互斥恢复参数失败后仍写入"

    run([str(RESTORE), str(backup_dir), "--apply", "--target-home", str(target)], env)
    restored_config = (target / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert str(target) in restored_config and str(source_home) not in restored_config
    assert list((target / ".ark" / "restore-reports").rglob("workbuddy-automations-restore-plan.json"))
    assert not list(target.rglob("automations-restore.sql"))
    target_hermes = (target / "AppData" / "Local" / "hermes") if os.name == "nt" else (target / ".hermes")
    assert (target_hermes / "skills" / "hermes-fixture" / "SKILL.md").is_file()
    assert (target / ".memory-tencentdb" / "memory-tdai" / "vectors.db").is_file()

    write(target / ".codex" / "config.toml", "locally changed\n")
    run([str(RESTORE), str(backup_dir), "--apply", "--target-home", str(target)], env)
    archived = list((target / ".ark" / "restore-conflicts").rglob("codex/config.toml"))
    assert archived and archived[-1].read_text(encoding="utf-8") == "locally changed\n"

    fresh_marker = target / ".codex" / "AGENTS.md"
    fresh_before = fresh_marker.read_bytes()
    run([str(RESTORE), str(backup_dir), "--apply", "--fresh", "--target-home", str(target)], env, expected=1)
    assert fresh_marker.read_bytes() == fresh_before
    run([str(RESTORE), str(backup_dir), "--apply-automations", "--target-home", str(target)], env, expected=1)

    unknown = hermes / "future-obscure-artifact"
    write(unknown, "must be classified\n")
    complete_fail_out = fixture / "complete-fail-must-not-exist"
    run([str(BACKUP), "--profile", "complete", "--out", str(complete_fail_out)], env, expected=1)
    assert not complete_fail_out.exists(), "complete fail-closed preview wrote output"
    unknown.unlink()

    hermes_config_path = hermes / "config.yaml"
    hermes_config_original = hermes_config_path.read_text(encoding="utf-8")
    write(
        hermes_config_path,
        hermes_config_original
        + "  unresolved-local:\n    command: missing-local-mcp-command\n    args: [-m, missing.module]\n",
    )
    unresolved_preview = run([str(BACKUP), "--profile", "complete"], env)
    assert "local-stdio-command-unresolved=1" in unresolved_preview.stdout
    unresolved_apply = fixture / "unresolved-local-apply-must-not-exist"
    run([str(BACKUP), "--profile", "complete", "--out", str(unresolved_apply), "--apply"],
        env, expected=1)
    assert not unresolved_apply.exists()
    write(hermes_config_path, hermes_config_original)

    jobs_path = hermes / "cron" / "jobs.json"
    jobs_original = jobs_path.read_text(encoding="utf-8")
    jobs_with_gap = json.loads(jobs_original)
    jobs_with_gap["jobs"].append({
        "id": "missing-script", "name": "missing script", "skills": [],
        "script": "does-not-exist.py", "workdir": str(project), "no_agent": True,
        "schedule": {"kind": "cron", "expr": "30 1 * * *"}, "enabled": True,
    })
    write(jobs_path, json.dumps(jobs_with_gap, ensure_ascii=False))
    gap_apply_out = fixture / "complete-gap-apply-must-not-exist"
    run([str(BACKUP), "--profile", "complete", "--out", str(gap_apply_out), "--apply"], env, expected=1)
    assert not gap_apply_out.exists(), "complete apply 带阻断 coverage gap 仍然出包"
    write(jobs_path, jobs_original)

    complete_mapping_only = fixture / "backup-complete-mappings-only"
    run([str(BACKUP), "--profile", "complete",
         "--out", str(complete_mapping_only), "--apply"], env)
    mapping_only_manifest = json.loads(
        (complete_mapping_only / "manifest.json").read_text(encoding="utf-8")
    )
    assert mapping_only_manifest["projectMappings"]
    assert all(item["contentIncluded"] is False
               for item in mapping_only_manifest["projectMappings"])
    assert not any(entry["relPath"].startswith("projects/")
                   for entry in mapping_only_manifest["entries"])

    complete_backup = fixture / "backup-complete"
    run([str(BACKUP), "--profile", "complete", "--projects",
         "--out", str(complete_backup), "--apply"], env)
    complete_manifest = json.loads((complete_backup / "manifest.json").read_text(encoding="utf-8"))
    assert complete_manifest["schemaVersion"] == "2.2"
    assert complete_manifest["options"]["profile"] == "complete"
    assert "hermes/gateway.heartbeat" not in {
        item["relPath"] for item in complete_manifest["entries"]
    }
    assert "hermes/state/gateway.heartbeat" not in {
        item["relPath"] for item in complete_manifest["entries"]
    }
    assert "hermes/skills/.usage.json" not in {
        item["relPath"] for item in complete_manifest["entries"]
    }
    assert not any("/__pycache__/" in item["relPath"]
                   for item in complete_manifest["entries"])
    assert {p["name"] for p in complete_manifest["profileRoots"]} == {"default", "researcher"}
    assert complete_manifest["desktopConsistency"]["status"] == "stable-at-scan"
    assert {(item["profile"], item["server"]) for item in complete_manifest["localMcpProjects"]} == {
        ("default", "fixture-local-managed"), ("default", "fixture-node-local"),
        ("researcher", "researcher-local"),
    }
    local_manifest = next(item for item in complete_manifest["localMcpProjects"]
                          if item["server"] == "fixture-local-managed")
    assert local_manifest["server"] == "fixture-local-managed"
    assert local_manifest["target"] == {
        "kind": "localappdata", "relativePath": "fixture-readonly-mcp",
        "requiresExplicitMapping": False,
    }
    assert local_manifest["commandRelativePath"].replace("\\", "/").endswith(".runtime/Scripts/python.exe") if os.name == "nt" else local_manifest["commandRelativePath"].endswith(".runtime/bin/python")
    assert local_manifest["runtimeRecipe"]["type"] == "python-uv-lock"
    assert local_manifest["runtimeRecipe"]["lockFile"] == "requirements.lock"
    assert local_manifest["installation"]["type"] == "hybrid-portable-v1"
    assert local_manifest["installation"]["nonExecutable"] is True
    assert local_manifest["installation"]["strategyOrder"] == [
        "trusted-source-when-verifiable", "embedded-source-fallback",
    ]
    assert local_manifest["installation"]["trustedSource"] is None
    assert local_manifest["installation"]["embeddedSourceFallback"] == {
        "type": "ark-archive-source",
        "archivePrefix": local_manifest["archivePrefix"],
        "lockFile": "requirements.lock",
        "role": "custom-project-source",
    }
    assert local_manifest["portableState"] == ["state/managed-playlists.json"]
    assert local_manifest["reauthorizationRequired"] is True
    assert {"Windows Credential Locker", "Chrome profile/Cookies", "Music User Token", "device-bound login"} <= set(local_manifest["excludedAccountState"])
    node_manifest = next(item for item in complete_manifest["localMcpProjects"]
                         if item["server"] == "fixture-node-local")
    assert node_manifest["runtimeRecipe"] == {
        "type": "node-npm-lock", "lockFile": "package-lock.json",
        "installMode": "npm-ci-ignore-scripts",
        "verification": {"type": "node-check", "argIndex": 0},
    }
    assert node_manifest["installation"]["runtime"] == {
        "name": "node", "packageManager": "npm", "recipeType": "node-npm-lock",
    }
    assert node_manifest["installation"]["trustedSource"]["package"]["package"] == node_package
    assert node_manifest["installation"]["packageProvenance"][0]["version"] == "7.0.0"
    assert node_manifest["commandName"] == "node"
    assert node_manifest["argsPathRewrites"] == [{
        "index": 0, "relativePath": f"node_modules/{node_package}/index.js",
    }]
    assert node_manifest["reauthorizationRequired"] is True
    assert "device-bound login" in node_manifest["excludedAccountState"]
    assert any(item.endswith("credentials") for item in node_manifest["excludedAccountState"])
    assert any(p["name"] == "memory_tencentdb" and p["included"]
               and p["gitTracked"] and p["gitDirty"]
               for p in complete_manifest["providerSources"])
    assert complete_manifest["projectMappings"] and complete_manifest["cronDependencies"]
    assert any(root["targetTemplate"] == "~/.agents/skills" for root in complete_manifest["externalRoots"])
    known_configs = {root.get("configClass") for root in complete_manifest["externalRoots"]}
    assert {"himalaya-config", "yescan-config", "opencli-config", "workbuddy-key-fallback"} <= known_configs
    cron_root = next(root for root in complete_manifest["externalRoots"] if root.get("includedBy") == "cron-script")
    assert (complete_backup / cron_root["archivePrefix"] / "notify.py").is_file()
    assert any(dep.get("scriptArtifact", "").endswith("/notify.py") for dep in complete_manifest["cronDependencies"])
    assert complete_manifest["links"] and complete_manifest["artifactClasses"]["link-topology"] >= 2
    assert (complete_backup / "hermes-provider" / "memory_tencentdb" / "provider.py").is_file()
    assert (complete_backup / "hermes" / "profiles" / "researcher" / "profile.yaml").is_file()
    assert (complete_backup / "hermes-desktop" / "Local Storage" / "leveldb" / "000003.ldb").is_file()
    assert not (complete_backup / "hermes-desktop" / "Local Storage" / "leveldb" / "LOCK").exists()
    assert not (complete_backup / "hermes-desktop" / "Network").exists()
    assert not (complete_backup / "hermes-desktop" / "connection.json").exists()
    local_archive = complete_backup / local_manifest["archivePrefix"]
    for rel in ("src/fixture_readonly_mcp/server.py", "pyproject.toml", "requirements.lock",
                "run-server.cmd", "scripts/probe_mcp.py", "tests/test_server.py",
                "README.md", "SPEC.md", "AGENTS.md", "state/managed-playlists.json"):
        assert (local_archive / rel).is_file(), rel
    for rel in (".runtime", ".venv-test", "build", ".git", "credentials",
                "state/.applemusic-mcp", "state/confirmations", "state/token.json"):
        assert not (local_archive / rel).exists(), rel
    node_archive = complete_backup / node_manifest["archivePrefix"]
    for rel in ("package.json", "package-lock.json", f"src/{node_package}/package.json",
                f"src/{node_package}/index.js"):
        assert (node_archive / rel).is_file(), rel
    assert not (node_archive / "node_modules").exists()
    assert not (node_archive / "credentials").exists()
    reauthorize = (complete_backup / "REAUTHORIZE.md").read_text(encoding="utf-8")
    assert "fixture-local-managed" in reauthorize and "fixture-node-local" in reauthorize
    installation_doc = (complete_backup / "INSTALLATION.md").read_text(encoding="utf-8")
    assert "non-executable" in installation_doc
    assert "fixture-local-managed" in installation_doc and "fixture-node-local" in installation_doc
    assert "embedded-source-fallback" in installation_doc and "Target install path" in installation_doc
    assert not any(entry["relPath"].startswith("hermes/profiles/researcher/state-snapshots/")
                   for entry in complete_manifest["entries"])
    assert any(item["originPath"].endswith("state-snapshots")
               and item["reason"] == "hermes-reinstallable-runtime-cache-or-live-state"
               for item in complete_manifest["excluded"])
    assert not (complete_backup / "hermes" / "kanban" / ".dispatcher.lock").exists()
    assert any(item["reason"] == "runtime-file"
               and item["originPath"].endswith(".dispatcher.lock")
               for item in complete_manifest["excluded"])
    assert (complete_backup / "projects" / "project" / "content" / "src" / "main.py").is_file()
    assert (complete_backup / "projects" / "project" / "content" / "data" / "project.db").is_file()
    assert (complete_backup / "projects" / "project" / "content" / ".git" / "HEAD").is_file()
    assert (complete_backup / "projects" / "project" / "content" / "logs" / "audit.log").is_file()
    assert (complete_backup / "projects" / "project" / "content" / "dist" / "release.txt").is_file()
    for tier in ("L0", "L1", "L2", "L3"):
        assert (complete_backup / "hermes-memory" / ".memory-tencentdb" / "memory-tdai" / tier).is_dir()
    assert not any(leaked_line_secret in path.read_text(encoding="utf-8", errors="ignore")
                   for path in complete_backup.rglob("*") if path.is_file())

    explicit_external_args: list[str] = []
    for root in complete_manifest["externalRoots"]:
        if root.get("requiresExplicitMapping"):
            explicit_external_args += [
                "--external-root-map",
                f"{root['id']}={fixture / 'restored-external' / root['id']}",
            ]

    unresolved_target = fixture / "complete-unresolved-target"
    complete_parts = "codex,workbuddy,hermes,hermes-memory,hermes-desktop,hermes-provider,external-roots,projects"
    run([str(RESTORE), str(complete_backup), "--apply", "--parts", complete_parts,
         "--target-platform", "linux", "--target-home", str(unresolved_target)], env, expected=1)
    assert not unresolved_target.exists(), "unmapped complete restore wrote target"

    complete_target = fixture / "complete-target"
    restored_project = fixture / "restored-project"
    run([str(RESTORE), str(complete_backup), "--apply", "--parts", complete_parts,
         "--target-platform", "linux", "--target-home", str(complete_target),
         "--project-map", f"project={restored_project}", *explicit_external_args], env)
    assert (complete_target / ".hermes" / "profiles" / "researcher" / "profile.yaml").is_file()
    assert (complete_target / ".hermes" / "plugins" / "memory" / "memory_tencentdb" / "provider.py").is_file()
    assert (complete_target / ".config" / "Hermes" / "Local Storage" / "leveldb" / "000003.ldb").is_file()
    assert (complete_target / ".agents" / "skills" / "external-skill" / "SKILL.md").is_file()
    restored_link = complete_target / ".hermes" / "skills" / "external-link"
    assert restored_link.exists() or (restored_link / ".ark-link-degraded.json").is_file()
    assert (restored_project / "src" / "main.py").is_file()
    with sqlite3.connect(restored_project / "data" / "project.db") as connection:
        assert connection.execute("SELECT value FROM data").fetchone()[0] == "portable project data"
    with sqlite3.connect(complete_target / ".hermes" / "projects.db") as connection:
        assert connection.execute("SELECT path FROM project_folders WHERE project_id='p1'").fetchone()[0] == str(restored_project)

    local_dry_target = fixture / "local-dry-target-must-not-exist"
    run([str(RESTORE), str(complete_backup), "--dry-run", "--parts", "hermes,local-mcp-projects",
         "--target-home", str(local_dry_target)], env)
    assert not local_dry_target.exists(), "local MCP dry-run wrote target"

    local_target = fixture / "local-mcp-target"
    run([str(RESTORE), str(complete_backup), "--apply", "--parts", "hermes,local-mcp-projects",
         "--target-home", str(local_target)], env)
    local_target_hermes = ((local_target / "AppData" / "Local" / "hermes")
                           if os.name == "nt" else local_target / ".hermes")
    restored_local = ((local_target / "AppData" / "Local" / "fixture-readonly-mcp")
                      if os.name == "nt" else local_target / ".local" / "share" / "fixture-readonly-mcp")
    runtime_python = restored_local / ".runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert runtime_python.is_file()
    imported = subprocess.run(
        [str(runtime_python), "-I", "-c", "import fixture_readonly_mcp.server"],
        capture_output=True, text=True,
    )
    assert imported.returncode == 0, imported.stderr
    restored_researcher = ((local_target / "AppData" / "Local" / "researcher-readonly-mcp")
                           if os.name == "nt" else local_target / ".local" / "share" / "researcher-readonly-mcp")
    researcher_python = restored_researcher / ".runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert researcher_python.is_file()
    researcher_config = (local_target_hermes / "profiles" / "researcher" / "config.yaml").read_text(encoding="utf-8")
    assert str(researcher_python) in researcher_config and str(source_home) not in researcher_config
    restored_local_config = (local_target_hermes / "config.yaml").read_text(encoding="utf-8")
    assert str(runtime_python) in restored_local_config
    assert str(restored_local / "state") in restored_local_config
    assert str(source_home) not in restored_local_config
    restored_node = ((local_target / "AppData" / "Local" / "fixture-node-mcp-root")
                     if os.name == "nt" else local_target / ".local" / "share" / "fixture-node-mcp-root")
    restored_node_entry = restored_node / "node_modules" / node_package / "index.js"
    assert restored_node_entry.is_file()
    checked = subprocess.run([shutil.which("node"), "--check", str(restored_node_entry)],
                             capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert str(restored_node_entry) in restored_local_config
    assert not (restored_local / "credentials").exists()
    assert not (restored_local / "state" / ".applemusic-mcp").exists()
    assert not (restored_node / "credentials").exists()
    local_reports = sorted((local_target / ".ark" / "restore-reports").rglob("restore-report.md"))
    assert local_reports
    local_report = local_reports[-1].read_text(encoding="utf-8")
    assert "passed-python-import" in local_report and "passed-node-check" in local_report
    assert "重新授权" in local_report

    complete_sandbox = fixture / "complete-verify-sandbox"
    run([str(VERIFY), str(complete_backup), "--sandbox-apply", str(complete_sandbox),
         "--parts", "hermes,hermes-memory,hermes-provider,local-mcp-projects",
         "--no-report"], env)
    assert (complete_sandbox / ".ark" / "restore-reports").is_dir()

    no_password = fixture / "credentials-no-password.zip"
    run([
        str(BACKUP), "--profile", "advanced", "--include-sensitive-config",
        "--out", str(no_password), "--apply",
    ], env, expected=1)
    assert not no_password.exists()

    encrypted = fixture / "credentials.zip"
    env["ARK_TEST_PASSWORD"] = "fixture-password-not-a-real-secret"
    run([
        str(BACKUP), "--profile", "complete", "--include-sensitive-config",
        "--password-env", "ARK_TEST_PASSWORD", "--out", str(encrypted), "--apply",
    ], env)
    assert encrypted.is_file() and not (fixture / "credentials").exists()
    with zipfile.ZipFile(encrypted) as ordinary:
        start_here = ordinary.read("ARK-START-HERE.txt")
        ai_contract = ordinary.read("AI-RESTORE.md").decode("utf-8")
        public_installation = ordinary.read("INSTALLATION.md").decode("utf-8")
        assert start_here.startswith(b"Ark 3.2")
        assert b"pyzipper pyyaml" in start_here
        assert "使用方舟技能恢复这个压缩包" in ai_contract
        assert "PyYAML" in ai_contract
        assert "INSTALLATION.md" in ai_contract and "non-executable" in ai_contract
        assert "non-executable" in public_installation
        bootstrap_path = fixture / "ARK-BOOTSTRAP.py"
        bootstrap_path.write_bytes(ordinary.read("ARK-BOOTSTRAP.py"))
        assert bootstrap_path.read_bytes().startswith(b"#!/usr/bin/env python3")
        assert ordinary.read("ark-tools/ark_restore.py")
    bootstrap_target = fixture / "bootstrap-target-must-not-exist"
    run([str(bootstrap_path), str(encrypted), "--dry-run", "--password-env", "ARK_TEST_PASSWORD",
         "--target-home", str(bootstrap_target)], env)
    assert not bootstrap_target.exists(), "one-file bootstrap dry-run wrote target"
    try:
        with zipfile.ZipFile(encrypted) as ordinary:
            ordinary.read("manifest.json")
        raise AssertionError("AES ZIP 可在无口令时读取")
    except (RuntimeError, NotImplementedError):
        pass
    encrypted_target = fixture / "encrypted-target"
    run([
        str(RESTORE), str(encrypted), "--dry-run", "--password-env", "ARK_TEST_PASSWORD",
        "--target-home", str(encrypted_target),
    ], env)
    assert not encrypted_target.exists()
    run([
        str(RESTORE), str(encrypted), "--apply", "--password-env", "ARK_TEST_PASSWORD",
        "--target-home", str(encrypted_target), *explicit_external_args,
    ], env)
    assert not (encrypted_target / ".codex" / "auth.json").exists(), "账号登录文件不应进入加密配置包"
    assert not (encrypted_target / ".codex" / ".credentials.json").exists(), "账号状态文件不应进入加密配置包"
    assert not (encrypted_target / ".codex" / "cookies").exists(), "Cookie 目录不应进入加密配置包"
    assert not (encrypted_target / ".workbuddy" / "credentials").exists(), "账号状态目录不应进入加密配置包"
    assert "fixture-portable-token" in (encrypted_target / ".workbuddy" / "mcp.json").read_text(encoding="utf-8")
    assert portable_key in (encrypted_target / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert large_secret in (encrypted_target / ".codex" / "skills" / "fixture-skill" / "large-secret.txt").read_text(encoding="utf-8")
    assert array_secret in (encrypted_target / ".codex" / "skills" / "fixture-skill" / "array-secret.json").read_text(encoding="utf-8")
    encrypted_hermes = (encrypted_target / "AppData" / "Local" / "hermes") if os.name == "nt" else (encrypted_target / ".hermes")
    restored_env = (encrypted_hermes / ".env").read_text(encoding="utf-8")
    assert "fixture-hermes-secret" in restored_env
    assert (encrypted_target / ".config" / "himalaya" / "secrets" / "qq.pass").read_text(encoding="utf-8").strip() == "fixture-mail-authorization-code"
    assert "fixture-yescan-key" in (encrypted_target / ".yescan" / "config.json").read_text(encoding="utf-8")
    assert "fixture-fallback-key" in (encrypted_target / ".workbuddy-key-fallback" / ".env").read_text(encoding="utf-8")
    assert (encrypted_target / ".memory-tencentdb" / "tdai-gateway.standalone.yaml").as_posix() in restored_env
    assert (encrypted_target / ".memory-tencentdb" / "memory-tdai").as_posix() in restored_env
    assert "source-user/MemoryCore" not in restored_env.replace("\\", "/")
    assert not any(
        line.lstrip().startswith("MEMORY_TENCENTDB_GATEWAY_CMD=")
        for line in restored_env.splitlines()
    )
    assert "use Hermes auto-discovery" in restored_env
    run([
        str(VERIFY), str(encrypted), "--password-env", "ARK_TEST_PASSWORD", "--no-report",
    ], env)

    malicious = fixture / "malicious.zip"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"schemaVersion": "2.0", "entries": []}))
        archive.writestr("../escaped.txt", "escape")
    run([str(RESTORE), str(malicious), "--dry-run", "--target-home", str(fixture / "malicious-target")], env, expected=1)
    assert not (fixture / "escaped.txt").exists()

    schema21 = {
        "schemaVersion": "2.1", "options": {"profile": "complete"}, "entries": [],
        "externalRoots": [], "links": [], "softwareInventory": [], "projectMappings": [],
        "postRestoreActions": [], "coverageGaps": [], "providerSources": [],
    }
    hostile_manifests = []
    bad_root = json.loads(json.dumps(schema21))
    bad_root["externalRoots"] = [{
        "id": "root-x", "archivePrefix": "external-roots/root-x",
        "targetTemplate": "~/../../escape",
    }]
    hostile_manifests.append(bad_root)
    bad_link = json.loads(json.dumps(schema21))
    bad_link["externalRoots"] = [{
        "id": "root-x", "archivePrefix": "external-roots/root-x",
        "targetTemplate": "~/.agents/skills",
    }]
    bad_link["links"] = [{
        "relPath": "hermes/skills/x", "externalRootId": "root-x",
        "targetRelativePath": "../../escape",
    }]
    hostile_manifests.append(bad_link)
    bad_gap = json.loads(json.dumps(schema21))
    bad_gap["coverageGaps"] = [{"class": "source-locked-or-unreadable", "path": "x"}]
    hostile_manifests.append(bad_gap)
    bad_provider = json.loads(json.dumps(schema21))
    bad_provider["providerSources"] = [{
        "name": "memory_tencentdb", "included": False, "gitDirty": True,
        "verifiedSource": None,
    }]
    hostile_manifests.append(bad_provider)
    bad_recipe = {
        "schemaVersion": "2.2", "options": {"profile": "basic"}, "entries": [],
        "externalRoots": [], "links": [], "softwareInventory": [], "projectMappings": [],
        "postRestoreActions": [], "coverageGaps": [], "providerSources": [],
        "localMcpProjects": [{
            "id": "evil", "server": "evil", "profile": "default",
            "archivePrefix": "local-mcp-projects/evil/content",
            "target": {"kind": "home", "relativePath": ".local/evil", "requiresExplicitMapping": False},
            "commandRelativePath": ".runtime/bin/python", "argsTemplate": [],
            "argsPathRewrites": [], "envPathRewrites": [],
            "runtimeRecipe": {"type": "shell", "lockFile": "lock", "command": "do anything"},
            "reauthorizationRequired": True, "portableState": [], "excludedAccountState": [],
        }],
    }
    hostile_manifests.append(bad_recipe)
    for index, hostile in enumerate(hostile_manifests):
        archive_path = fixture / f"hostile-manifest-{index}.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(hostile))
        hostile_target = fixture / f"hostile-target-{index}"
        run([str(RESTORE), str(archive_path), "--apply", "--target-home", str(hostile_target)],
            env, expected=1)
        assert not hostile_target.exists()

    corrupt_backup = fixture / "backup-corrupt"
    shutil.copytree(backup_dir, corrupt_backup)
    write(corrupt_backup / "codex" / "AGENTS.md", "tampered\n")
    corrupt_target = fixture / "corrupt-target"
    run([str(RESTORE), str(corrupt_backup), "--apply", "--target-home", str(corrupt_target)],
        env, expected=1)
    assert not corrupt_target.exists(), "archive preflight failure mutated target"

    sys.path.insert(0, str(ROOT / "scripts"))
    import ark_restore as restore_module
    import ark_backup as backup_module
    import ark_common as common_module
    assert not backup_module._safe_local_mcp_root(common_module.home_dir())
    current_localappdata = Path(os.environ.get("LOCALAPPDATA", common_module.home_dir() / "AppData" / "Local"))
    assert not backup_module._safe_local_mcp_root(current_localappdata)
    assert backup_module._safe_local_mcp_root(local_mcp)
    original_archive_existing = restore_module.archive_existing
    link_errors: list[str] = []
    try:
        def fail_link_archive(*_args, **_kwargs):
            raise FileExistsError("fixture conflict archive failure")
        restore_module.archive_existing = fail_link_archive
        had_old, mutated = restore_module.create_portable_link({
            "target": fixture / "link-target", "destination": fixture / "link-destination",
            "rel": "codex/link", "linkType": "symlink", "isDirectory": False,
        }, fixture / "link-conflicts", link_errors, [])
        assert not had_old and not mutated and link_errors
    finally:
        restore_module.archive_existing = original_archive_existing

    transaction_manifest = {
        "localMcpProjects": [{
            "id": "transaction-node", "server": "transaction-node", "profile": "default",
            "target": {
                "kind": "home", "relativePath": ".local/share/fixture-node",
                "requiresExplicitMapping": False,
            },
            "commandName": "node",
            "argsTemplate": ["C:/source/node_modules/fixture-node-mcp/index.js"],
            "argsPathRewrites": [{
                "index": 0, "relativePath": "node_modules/fixture-node-mcp/index.js",
            }],
            "envPathRewrites": [],
            "runtimeRecipe": {"type": "node-npm-lock"},
        }],
    }
    transaction_original = (
        "mcp_servers:\n  transaction-node:\n    command: node\n"
        "    args:\n      - C:/source/node_modules/fixture-node-mcp/index.js\n"
    )
    transaction_home = fixture / "transaction-skipped-home"
    transaction_hermes = transaction_home / "hermes"
    transaction_config = transaction_hermes / "config.yaml"
    write(transaction_config, transaction_original)
    transaction_conflicts = transaction_home / ".ark" / "restore-conflicts" / "forced"
    transaction_changes: list[tuple[str, Path, bool]] = []
    try:
        rewritten = restore_module.rewrite_local_mcp_configs(
            transaction_manifest, transaction_home, transaction_hermes,
            {"hermes", "local-mcp-projects"}, {}, restore_module._target_platform(),
            transaction_conflicts, transaction_changes,
        )
        assert rewritten == [str(transaction_config)]
        assert transaction_changes == [("hermes/config.yaml", transaction_config, True)]
        assert (transaction_conflicts / "hermes" / "config.yaml").read_text(
            encoding="utf-8") == transaction_original
        raise RuntimeError("forced post-copy rewrite failure")
    except RuntimeError as exc:
        assert str(exc) == "forced post-copy rewrite failure"
        assert not restore_module.rollback_changes(transaction_changes, transaction_conflicts)
    assert transaction_config.read_text(encoding="utf-8") == transaction_original

    copied_home = fixture / "transaction-copied-home"
    copied_hermes = copied_home / "hermes"
    copied_config = copied_hermes / "config.yaml"
    copied_preexisting = "mcp_servers: {}\n"
    write(copied_config, copied_preexisting)
    copied_conflicts = copied_home / ".ark" / "restore-conflicts" / "forced"
    copied_had_old = restore_module.archive_existing(
        copied_config, copied_conflicts, "hermes/config.yaml")
    copied_changes = [("hermes/config.yaml", copied_config, copied_had_old)]
    write(copied_config, transaction_original)
    restore_module.rewrite_local_mcp_configs(
        transaction_manifest, copied_home, copied_hermes,
        {"hermes", "local-mcp-projects"}, {}, restore_module._target_platform(),
        copied_conflicts, copied_changes,
    )
    assert copied_changes == [("hermes/config.yaml", copied_config, True)]
    assert (copied_conflicts / "hermes" / "config.yaml").read_text(
        encoding="utf-8") == copied_preexisting
    assert not restore_module.rollback_changes(copied_changes, copied_conflicts)
    assert copied_config.read_text(encoding="utf-8") == copied_preexisting

    summary = {
        "status": "passed",
        "fixture": str(fixture),
        "fixtureKept": os.environ.get("ARK_KEEP_TEST_FIXTURE") == "1",
        "suite": "full-regression",
        "backupEntries": len(manifest["entries"]),
    }
    if not summary["fixtureKept"]:
        try:
            connection.close()
        except Exception:
            pass
        gc.collect()
        remove_fixture_safely(fixture)
        summary["fixtureCleaned"] = not fixture.exists()
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
