"""Test installer and package-validation failure boundaries without downloads."""

import hashlib
import struct
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
android_build = importlib.import_module("android_build")


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
                    patch.object(dev, "import_and_smoke"), patch.object(android_build, "prepare_gradle"), patch.object(dev, "run", side_effect=export), \
                    patch.object(inspector, "inspect_apk", return_value={}):
                with self.assertRaisesRegex(RuntimeError, "changed during export"):
                    dev.export_android({"godot": "unused", "host": "linux"}, {})
            self.assertEqual(list((root / "build").iterdir()), [])

    def test_export_excludes_local_android_build_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {
                "project.godot": "config_version=5\n",
                "android/build/build.gradle": "stale build recipe",
                "android/build/libs/stale.so": "stale native library",
                "android/plugins/keep.gdap": "local plugin configuration",
                "assets/build/keep.txt": "ordinary project resource",
                ".godot/stale": "old import cache",
            }
            for name, content in files.items():
                path = root / "app" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

            def import_project(config, env, project):
                self.assertFalse((project / "android/build").exists())
                self.assertFalse((project / ".godot").exists())
                for name in ("android/plugins/keep.gdap", "assets/build/keep.txt"):
                    self.assertEqual((project / name).read_text(), files[name])

            def export(command, *args, **kwargs):
                Path(command[-1]).write_bytes(b"mock APK")

            config = {"godot": "unused", "host": "linux", "lock_sha256": "b" * 64}
            identity = {"source_sha": "a" * 40, "source_dirty": False}
            with patch.object(dev, "ROOT", root), patch.object(dev, "source_identity", return_value=identity), \
                    patch.object(dev, "import_and_smoke", side_effect=import_project), \
                    patch.object(android_build, "prepare_gradle"), patch.object(dev, "run", side_effect=export), \
                    patch.object(inspector, "inspect_apk", return_value={"apk_sha256": "c" * 64}):
                with contextlib.redirect_stdout(io.StringIO()):
                    dev.export_android(config, {})
            self.assertTrue((root / "build/questos-p1-unsigned.apk").is_file())
            for name, content in files.items():
                self.assertEqual((root / "app" / name).read_text(), content)

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
                    patch.object(dev, "source_identity", return_value=identity), patch.object(dev, "import_and_smoke"), patch.object(android_build, "prepare_gradle"), \
                    patch.object(dev, "run", side_effect=export), patch.object(inspector, "inspect_apk", return_value={"apk_sha256": "c" * 64}):
                with contextlib.redirect_stdout(io.StringIO()):
                    dev.export_android(config, {})
            record = json.loads((root / "build/build-manifest.json").read_text())
            self.assertEqual(record["toolchain_lock_sha256"], config["lock_sha256"])
            self.assertNotEqual(record["toolchain_lock_sha256"], bootstrap.sha256(lock_path))

    def test_package_permissions_abi_loader_mode_and_signatures_are_checked(self):
        base = "package: name='org.johnsondev.questos.dev' versionCode='2' versionName='0.1.0-p1'\nminSdkVersion:'29'\ntargetSdkVersion:'32'\nnative-code: 'arm64-v8a'\n"
        base += "".join(f"uses-permission: name='{p}'\n" for p in inspector.PERMISSIONS)
        manifest = (ROOT / "tests/fixtures/p1-manifest.txt").read_text()
        elf = b"\x7fELF\x02\x01" + b"\0" * 12 + struct.pack('<H', 183)
        cases = [({}, True), ({"badging": "uses-permission: name='android.permission.CAMERA'\n"}, False),
                 ({"extra": "lib/x86/libbad.so"}, False), ({"extra": "META-INF/SIGNER.RSA"}, False),
                 ({"command": b"--xr_mode_regular"}, False), ({"loader": b"wrong loader"}, False),
                 ({"engine": b"not ELF"}, False), ({"manifest": manifest.replace('com.oculus.intent.category.VR', 'wrong')}, False),
                 ({"manifest": manifest.replace('com.godot.game.GodotApp" (Raw:', 'wrong" (Raw:')}, False)]
        for changes, expected in cases:
            with self.subTest(changes=changes.keys()), tempfile.TemporaryDirectory() as temporary:
                apk = Path(temporary) / "sample.apk"
                with zipfile.ZipFile(apk, "w") as z:
                    z.writestr("lib/arm64-v8a/libgodot_android.so", changes.get("engine", elf))
                    z.writestr("lib/arm64-v8a/libopenxr_loader.so", changes.get("loader", elf))
                    z.writestr("assets/_cl_", changes.get("command", b"--xr_mode_openxr"))
                    if "extra" in changes:
                        z.writestr(changes["extra"], b"fixture")
                responses = [subprocess.CompletedProcess([], 0, base + changes.get("badging", ""), ""),
                             subprocess.CompletedProcess([], 0, changes.get("manifest", manifest), "")]
                config = {"host": "linux", "android_home": temporary, "toolchain": {"android_build_tools": "36.0.0", "openxr_loader": "1.1.54", "openxr_loader_arm64_sha256": hashlib.sha256(elf).hexdigest()}}
                with patch.object(inspector.subprocess, "run", side_effect=responses):
                    if expected:
                        self.assertTrue(inspector.inspect_apk(apk, config, {})["xr_headset_candidate"])
                    else:
                        with self.assertRaises(RuntimeError):
                            inspector.inspect_apk(apk, config, {})

    def test_xr_metadata_values_must_belong_to_application_scope(self):
        manifest = (ROOT / "tests/fixtures/p1-manifest.txt").read_text()
        # Keep all tokens, but put the supportedDevices value on a different entry.
        wrong = manifest.replace('="quest2" (Raw: "quest2")', '="wrong" (Raw: "wrong")')
        wrong += '\n      E: meta-data\n        A: android:name="com.oculus.supportedDevices"\n        A: android:value="quest2"\n'
        with self.assertRaisesRegex(RuntimeError, "metadata"):
            inspector.validate_xr_manifest(wrong)


if __name__ == "__main__":
    unittest.main()
