from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ark_backup as backup  # noqa: E402
import ark_common as common  # noqa: E402
import ark_restore as restore  # noqa: E402


def node_recipe(marker: object = ...) -> dict:
    recipe = {
        "type": "node-npm-lock",
        "lockFile": "package-lock.json",
        "installMode": "npm-ci-ignore-scripts",
        "verification": {"type": "node-check", "argIndex": 0},
    }
    if marker is not ...:
        recipe["nativeCredentialAddon"] = marker
    return recipe


def node_lock(include_keytar: bool = False) -> bytes:
    root: dict[str, object] = {"name": "fixture", "dependencies": {}}
    packages: dict[str, object] = {"": root}
    if include_keytar:
        root["optionalDependencies"] = {"keytar": "7.9.0"}
        entry = dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
        entry.pop("type")
        packages["node_modules/keytar"] = entry
    return json.dumps({"lockfileVersion": 3, "packages": packages}, sort_keys=True).encode("utf-8")


def node_manifest(marker: object = ..., lock_bytes: bytes | None = None) -> dict:
    manifest = {
        "schemaVersion": "2.2",
        "options": {"profile": "basic"},
        "entries": [],
        "externalRoots": [],
        "links": [],
        "softwareInventory": [],
        "projectMappings": [],
        "postRestoreActions": [],
        "coverageGaps": [],
        "providerSources": [],
        "localMcpProjects": [{
            "id": "default-ms365",
            "server": "ms365",
            "profile": "default",
            "archivePrefix": "local-mcp-projects/default-ms365/content",
            "target": {
                "kind": "home",
                "relativePath": ".local/share/ms365-mcp",
                "requiresExplicitMapping": False,
            },
            "commandName": "node",
            "argsTemplate": ["C:/source/node_modules/@softeria/ms-365-mcp-server/dist/index.js"],
            "argsPathRewrites": [{
                "index": 0,
                "relativePath": "node_modules/@softeria/ms-365-mcp-server/dist/index.js",
            }],
            "envPathRewrites": [],
            "runtimeRecipe": node_recipe(marker),
            "reauthorizationRequired": True,
            "portableState": [],
            "excludedAccountState": [],
        }],
    }
    item = manifest["localMcpProjects"][0]
    if lock_bytes is None:
        lock_bytes = node_lock(marker is not ...)
    item["installation"] = common.build_local_mcp_installation(item, lock_bytes)
    lock_rel = f"{item['archivePrefix']}/package-lock.json"
    manifest["entries"] = [{
        "relPath": lock_rel,
        "sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "artifactClass": "local-mcp-project-source",
    }]
    return manifest


class KeytarLockDetectionTests(unittest.TestCase):
    def write_lock(self, root: Path, keytar_entry: object = ...) -> Path:
        packages: dict[str, object] = {"": {"name": "fixture"}}
        if keytar_entry is not ...:
            packages["node_modules/keytar"] = keytar_entry
        lock = root / "package-lock.json"
        lock.write_text(json.dumps({"lockfileVersion": 3, "packages": packages}), encoding="utf-8")
        return lock

    def test_exact_anchor_adds_fixed_marker_and_absent_keytar_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            trusted_entry = dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
            trusted_entry.pop("type")
            trusted_entry["optional"] = True
            lock = self.write_lock(root, trusted_entry)
            collector = SimpleNamespace(m={"coverageGaps": []})
            recipe = node_recipe()
            backup._apply_node_native_credential_addon(
                collector, recipe, lock, "default", "ms365"
            )
            self.assertEqual(
                recipe["nativeCredentialAddon"],
                common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON,
            )
            self.assertEqual(collector.m["coverageGaps"], [])

            absent_lock = self.write_lock(root)
            absent_recipe = node_recipe()
            backup._apply_node_native_credential_addon(
                collector, absent_recipe, absent_lock, "default", "ordinary-node"
            )
            self.assertNotIn("nativeCredentialAddon", absent_recipe)
            self.assertEqual(collector.m["coverageGaps"], [])

    def test_mismatched_keytar_adds_blocking_coverage_gap(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            mismatched = dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
            mismatched.pop("type")
            mismatched["version"] = "7.9.1"
            lock = self.write_lock(root, mismatched)
            collector = SimpleNamespace(m={"coverageGaps": []})
            recipe = node_recipe()
            backup._apply_node_native_credential_addon(
                collector, recipe, lock, "default", "ms365"
            )
            self.assertNotIn("nativeCredentialAddon", recipe)
            self.assertEqual(
                collector.m["coverageGaps"][0]["class"],
                "local-stdio-keytar-trust-anchor-mismatch",
            )
            self.assertNotIn(
                collector.m["coverageGaps"][0]["class"],
                backup.COMPLETE_NONBLOCKING_GAP_CLASSES,
            )


class KeytarManifestValidationTests(unittest.TestCase):
    def test_marker_absent_or_exact_is_accepted(self) -> None:
        restore.validate_manifest(node_manifest())
        restore.validate_manifest(node_manifest(
            dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
        ))

    def test_tampered_marker_is_rejected(self) -> None:
        mutations = {
            "type": "arbitrary-native-addon",
            "version": "7.9.1",
            "resolved": "https://example.invalid/keytar.tgz",
            "integrity": "sha512-tampered",
            "hasInstallScript": 1,
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                marker = copy.deepcopy(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
                marker[field] = value
                with self.assertRaises(SystemExit):
                    restore.validate_manifest(node_manifest(marker))
        extra = copy.deepcopy(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
        extra["command"] = "npm rebuild anything"
        with self.assertRaises(SystemExit):
            restore.validate_manifest(node_manifest(extra))

    def test_sec003_marker_is_rederived_from_embedded_lock(self) -> None:
        marker = dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON)
        manifest = node_manifest(marker, node_lock(False))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item = manifest["localMcpProjects"][0]
            lock_path = root / item["archivePrefix"] / "package-lock.json"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_bytes(node_lock(False))
            reader = restore.BackupReader(str(root), None)
            try:
                with self.assertRaisesRegex(SystemExit, "addon.*lock|lock.*addon"):
                    restore.validate_installation_evidence(reader, manifest)
            finally:
                reader.close()

        trusted_manifest = node_manifest(marker, node_lock(True))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item = trusted_manifest["localMcpProjects"][0]
            lock_path = root / item["archivePrefix"] / "package-lock.json"
            lock_path.parent.mkdir(parents=True)
            lock_path.write_bytes(node_lock(True))
            reader = restore.BackupReader(str(root), None)
            try:
                restore.validate_installation_evidence(reader, trusted_manifest)
            finally:
                reader.close()


class KeytarRestoreExecutionTests(unittest.TestCase):
    def test_restore_uses_only_fixed_argv_and_bootstrap_embeds_executor(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            root = home / ".local" / "share" / "ms365-mcp"
            root.mkdir(parents=True)
            lock_bytes = node_lock(True)
            (root / "package-lock.json").write_bytes(lock_bytes)
            calls: list[tuple[list[str], Path, str]] = []

            def fake_run(argv: list[str], cwd: Path, label: str) -> str:
                calls.append((list(argv), cwd, label))
                return ""

            manifest = node_manifest(
                dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON), lock_bytes
            )
            with mock.patch.object(restore, "_run_recipe", side_effect=fake_run), mock.patch.object(
                restore.shutil, "which", side_effect=lambda name: f"{name}-bin"
            ):
                result = restore.rebuild_local_mcp_runtimes(
                    manifest,
                    home,
                    {"local-mcp-projects"},
                    {},
                    "linux",
                    home / "conflicts",
                    [],
                )

            entry = str(root / "node_modules/@softeria/ms-365-mcp-server/dist/index.js")
            self.assertEqual([call[0] for call in calls], [
                ["npm-bin", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                ["npm-bin", "rebuild", "keytar", "--foreground-scripts", "--no-audit", "--no-fund"],
                ["node-bin", "-e", "require('keytar')"],
                ["node-bin", "--check", entry],
            ])
            self.assertEqual(
                result[0]["codeHealth"],
                "passed-node-check+credential-addon-verified",
            )

            embedded = backup.bootstrap_files()["ark-tools/ark_restore.py"]
            self.assertEqual(embedded, Path(restore.__file__).read_bytes())
            self.assertIn(b"nativeCredentialAddon", embedded)
            self.assertIn(b"require('keytar')", embedded)

    def test_keytar_verification_failure_propagates_for_transaction_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            root = home / ".local" / "share" / "ms365-mcp"
            root.mkdir(parents=True)
            lock_bytes = node_lock(True)
            (root / "package-lock.json").write_bytes(lock_bytes)

            def fail_keytar(argv: list[str], cwd: Path, label: str) -> str:
                if argv[:3] == ["node-bin", "-e", "require('keytar')"]:
                    raise RuntimeError("keytar binding unavailable")
                return ""

            changed: list[tuple[str, Path, bool]] = []
            with mock.patch.object(restore, "_run_recipe", side_effect=fail_keytar), mock.patch.object(
                restore.shutil, "which", side_effect=lambda name: f"{name}-bin"
            ):
                with self.assertRaisesRegex(RuntimeError, "keytar binding unavailable"):
                    restore.rebuild_local_mcp_runtimes(
                        node_manifest(
                            dict(common.TRUSTED_KEYTAR_NATIVE_CREDENTIAL_ADDON), lock_bytes
                        ),
                        home,
                        {"local-mcp-projects"},
                        {},
                        "linux",
                        home / "conflicts",
                        changed,
                    )
            self.assertEqual(changed[0][0], "local-mcp-projects/default-ms365/node_modules")


if __name__ == "__main__":
    unittest.main()
