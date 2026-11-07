"""Test installer and package-validation failure boundaries without downloads."""

import hashlib
import contextlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
bootstrap = importlib.import_module("bootstrap")
inspector = importlib.import_module("inspect_apk")
dev = importlib.import_module("dev")


class ToolchainTests(unittest.TestCase):
    def test_archive_path_traversal_is_rejected_on_both_host_styles(self):
        for name in ["../escape", "/absolute", "C:/escape", "..\\escape", "\\\\server\\share\\file"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = root / "bad.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    z.writestr(name, "unsafe")
                with self.assertRaises(RuntimeError):
                    bootstrap.extract(archive, root / "out")

    def test_corrupt_cached_download_is_not_extracted_or_redownloaded_silently(self):
        with tempfile.TemporaryDirectory() as temporary:
            tools = Path(temporary)
            (tools / "downloads").mkdir()
            (tools / "downloads/tool.zip").write_bytes(b"changed")
            asset = {"file": "tool.zip", "url": "https://invalid.example/tool.zip", "sha256": hashlib.sha256(b"original").hexdigest()}
            with patch.object(bootstrap, "TOOLS", tools), patch.object(bootstrap.urllib.request, "urlopen", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(RuntimeError, "checksum"):
                    bootstrap.download(asset)

    def test_incomplete_install_is_repaired_despite_an_existing_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            tools = Path(temporary)
            archive = tools / "tool.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("root/tool", "working")
            destination = tools / "installed"
            destination.mkdir()
            asset = {"file": "tool.zip", "sha256": bootstrap.sha256(archive)}
            (destination / ".questos-install.json").write_text(json.dumps({"sha256": asset["sha256"], "required": ["tool"]}))
            with patch.object(bootstrap, "TOOLS", tools), patch.object(bootstrap, "download", return_value=archive):
                bootstrap.install(asset, destination, ["tool"], prefix="root")
            self.assertEqual((destination / "tool").read_text(), "working")

    def test_android_license_gate_precedes_downloads(self):
        with patch.object(bootstrap, "download", side_effect=AssertionError("download")):
            with self.assertRaisesRegex(RuntimeError, "acceptance"):
                bootstrap.setup(android=True, accept_android_license=False)

    def test_truncated_receipt_is_repaired(self):
        with tempfile.TemporaryDirectory() as temporary:
            tools = Path(temporary)
            archive = tools / "tool.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("tool", "working")
            destination = tools / "installed"
            destination.mkdir()
            (destination / ".questos-install.json").write_text('{"sha256":')
            asset = {"file": "tool.zip", "sha256": bootstrap.sha256(archive)}
            with patch.object(bootstrap, "TOOLS", tools), patch.object(bootstrap, "download", return_value=archive):
                bootstrap.install(asset, destination, ["tool"])
            self.assertEqual(json.loads((destination / ".questos-install.json").read_text())["sha256"], asset["sha256"])

    def test_export_does_not_publish_if_checkout_revision_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app/project.godot").write_text("config_version=5\n")

            def export(command, *args, **kwargs):
                Path(command[-1]).write_bytes(b"mock APK")

            identities = [{"source_sha": "a" * 40, "source_dirty": False}, {"source_sha": "b" * 40, "source_dirty": False}]
            with patch.object(dev, "ROOT", root), patch.object(dev, "source_identity", side_effect=identities), \
                    patch.object(dev, "import_and_smoke"), patch.object(dev, "run", side_effect=export), \
                    patch.object(inspector, "inspect_apk", return_value={}):
                with self.assertRaisesRegex(RuntimeError, "changed during export"):
                    dev.export_android({"godot": "unused", "host": "linux"}, {})
            self.assertEqual(list((root / "build").iterdir()), [])

    def test_export_records_validated_toolchain_even_if_lock_is_edited(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app").mkdir()
            (root / "app/project.godot").write_text("config_version=5\n")
            lock_path = root / "toolchain.lock.json"
            lock_path.write_text('{"changed": true}')

            def export(command, *args, **kwargs):
                Path(command[-1]).write_bytes(b"mock APK")

            identity = {"source_sha": "a" * 40, "source_dirty": True}
            config = {"godot": "unused", "host": "linux", "lock_sha256": "b" * 64}
            with patch.object(dev, "ROOT", root), patch.object(dev, "LOCK", lock_path), \
                    patch.object(dev, "source_identity", return_value=identity), patch.object(dev, "import_and_smoke"), \
                    patch.object(dev, "run", side_effect=export), patch.object(inspector, "inspect_apk", return_value={"apk_sha256": "c" * 64}):
                with contextlib.redirect_stdout(io.StringIO()):
                    dev.export_android(config, {})
            record = json.loads((root / "build/build-manifest.json").read_text())
            self.assertEqual(record["toolchain_lock_sha256"], config["lock_sha256"])
            self.assertNotEqual(record["toolchain_lock_sha256"], bootstrap.sha256(lock_path))

    def test_package_permissions_abi_and_signatures_are_checked(self):
        base = "package: name='org.johnsondev.questos.dev' versionCode='1' versionName='0.1.0-dev'\nminSdkVersion:'24'\ntargetSdkVersion:'36'\nnative-code: 'arm64-v8a'\n"
        cases = [([], "", True), ([], "uses-permission: name='android.permission.CAMERA'\n", False),
                 (["lib/x86/libbad.so"], "", False), (["META-INF/SIGNER.RSA"], "", False)]
        for extra, extra_badging, expected in cases:
            with self.subTest(extra=extra, badging=extra_badging), tempfile.TemporaryDirectory() as temporary:
                apk = Path(temporary) / "sample.apk"
                with zipfile.ZipFile(apk, "w") as z:
                    z.writestr("lib/arm64-v8a/libgodot_android.so", b"fixture")
                    z.writestr("assets/_cl_", b"--xr_mode_regular")
                    for path in extra:
                        z.writestr(path, b"fixture")
                responses = [subprocess.CompletedProcess([], 0, base + extra_badging, ""),
                             subprocess.CompletedProcess([], 0, "android.intent.category.LAUNCHER", "")]
                with patch.object(inspector.subprocess, "run", side_effect=responses):
                    if expected:
                        self.assertEqual(inspector.inspect_apk(apk, {"host": "linux", "android_home": temporary, "toolchain": {"android_build_tools": "36.0.0"}}, {})["signing"], "unsigned")
                    else:
                        with self.assertRaises(RuntimeError):
                            inspector.inspect_apk(apk, {"host": "linux", "android_home": temporary, "toolchain": {"android_build_tools": "36.0.0"}}, {})


if __name__ == "__main__":
    unittest.main()
