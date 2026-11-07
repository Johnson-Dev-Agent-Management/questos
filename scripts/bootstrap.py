#!/usr/bin/env python3
"""Install the locked, project-local toolchain on Linux x64 or Windows x64."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
LOCK = ROOT / "toolchain.lock.json"
ANDROID_TERMS = "https://developer.android.com/studio/terms"


def host_key():
    machine = platform.machine().lower()
    if machine not in ("amd64", "x86_64"):
        raise RuntimeError("This toolchain supports x64 hosts. Use an x64 Windows PC or x64 Linux/WSL environment.")
    system = platform.system().lower()
    if system not in ("linux", "windows"):
        raise RuntimeError("Supported hosts: Windows x64 and Linux x64 (including WSL2).")
    return system


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(asset):
    cache = TOOLS / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / asset["file"]
    if target.exists():
        if sha256(target) == asset["sha256"]:
            return target
        raise RuntimeError(f"Cached download failed its checksum: {target}. Remove that file and retry.")
    temporary = target.with_suffix(target.suffix + ".partial")
    print(f"Downloading {asset['file']}", flush=True)
    try:
        with urllib.request.urlopen(asset["url"], timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        if sha256(temporary) != asset["sha256"]:
            raise RuntimeError(f"Download checksum mismatch: {asset['file']}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def safe_zip_member(name):
    # Check Windows drive/UNC forms even when extracting on Linux.
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise RuntimeError(f"Unsafe archive member: {name}")
    return path


def extract(archive, destination, members=None):
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive) as source:
            source.extractall(destination, filter="data")
        return
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            path = safe_zip_member(entry.filename)
            if members is not None and entry.filename not in members:
                continue
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Unexpected ZIP symlink: {entry.filename}")
            output = destination.joinpath(*path.parts)
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as incoming, output.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            if os.name != "nt" and mode & 0o111:
                output.chmod(0o755)


def install(asset, destination, required, prefix="", members=None):
    """Use a staging directory; an interrupted extraction never counts as installed."""
    receipt = destination / ".questos-install.json"
    wanted = {"sha256": asset["sha256"], "required": required}
    if receipt.is_file():
        if json.loads(receipt.read_text()) == wanted and all((destination / p).is_file() for p in required):
            return
    archive = download(asset)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="questos-install-", dir=TOOLS) as temporary:
        stage = Path(temporary)
        extract(archive, stage, members)
        content = stage / prefix if prefix else stage
        if not all((content / p).is_file() for p in required):
            raise RuntimeError(f"Archive layout changed: {asset['file']}")
        # Only tool-managed destinations are replaced; never global SDKs/editors.
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(content, destination, symlinks=True)
    receipt.write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")


def write_editor_settings(godot_dir, jdk=None, sdk=None):
    (godot_dir / "_sc_").touch()  # Godot self-contained mode: preserve global editor settings.
    settings_dir = godot_dir / "editor_data"
    settings_dir.mkdir(exist_ok=True)
    path = settings_dir / "editor_settings-4.6.tres"
    text = path.read_text(encoding="utf-8") if path.exists() else '[gd_resource type="EditorSettings" format=3]\n\n[resource]\n'
    values = {"filesystem/import/blender/enabled": "false"}
    if jdk and sdk:
        values.update({"export/android/java_sdk_path": json.dumps(jdk.as_posix()),
                       "export/android/android_sdk_path": json.dumps(sdk.as_posix())})
    lines = [line for line in text.splitlines() if line.split(" = ", 1)[0] not in values]
    path.write_text("\n".join(lines) + "\n" + "\n".join(f"{key} = {value}" for key, value in values.items()) + "\n", encoding="utf-8")


def setup(android=False, accept_android_license=False):
    host = host_key()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    assets = lock["assets"]
    if android and not accept_android_license:
        raise RuntimeError(f"Android SDK installation requires acceptance of {ANDROID_TERMS}. Review the terms and rerun with --accept-android-sdk-license.")
    TOOLS.mkdir(exist_ok=True)
    godot_dir = TOOLS / ("godot-" + lock["godot_version"])
    binary = "Godot_v4.6.3-stable_win64_console.exe" if host == "windows" else "Godot_v4.6.3-stable_linux.x86_64"
    required = [binary]
    if host == "windows":
        required.append("Godot_v4.6.3-stable_win64.exe")
    install(assets["godot_" + host], godot_dir, required)
    if host == "linux":
        (godot_dir / binary).chmod(0o755)
    jdk, sdk = None, None
    if android:
        suffix = ".exe" if host == "windows" else ""
        jdk = TOOLS / ("jdk-" + lock["java_version"])
        install(assets["jdk_" + host], jdk, ["bin/java" + suffix, "bin/keytool" + suffix], prefix="jdk-" + lock["java_version"])
        sdk = TOOLS / "android-sdk"
        install(assets["platform_tools_" + host], sdk / "platform-tools", ["adb" + suffix], prefix="platform-tools")
        install(assets["build_tools_" + host], sdk / "build-tools" / lock["android_build_tools"], ["aapt2" + suffix, "lib/apksigner.jar"], prefix=lock["build_tools_archive_root"])
        install(assets["platform_all"], sdk / "platforms" / f"android-{lock['android_platform']}", ["android.jar"], prefix=lock["platform_archive_root"])
        template_dir = godot_dir / "editor_data/export_templates/4.6.3.stable"
        template_files = ["android_debug.apk", "android_release.apk"]
        install(assets["templates"], template_dir, template_files, prefix="templates",
                members={"templates/" + name for name in template_files})
        (sdk / ".questos-license-acceptance.json").write_text(json.dumps({"terms": ANDROID_TERMS, "acceptance": "explicit --accept-android-sdk-license option"}, indent=2) + "\n", encoding="utf-8")
    write_editor_settings(godot_dir, jdk, sdk)
    config = {"schema_version": 1, "host": host, "godot": str(godot_dir / binary),
              "lock_sha256": sha256(LOCK), "java_home": str(jdk) if jdk else None,
              "android_home": str(sdk) if sdk else None}
    # Preserve a previously installed Android setup when refreshing editor-only mode.
    env_path = TOOLS / "environment.json"
    if not android and env_path.exists():
        old = json.loads(env_path.read_text())
        if old.get("lock_sha256") == config["lock_sha256"]:
            config.update({key: old.get(key) for key in ("java_home", "android_home")})
    env_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    subprocess.run([config["godot"], "--headless", "--version"], check=True)
    print("Toolchain ready. Run: python scripts/dev.py doctor", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", action="store_true", help="also install the pinned JDK, Android SDK components, and Android export templates")
    parser.add_argument("--accept-android-sdk-license", action="store_true", help="accept the Android SDK terms linked in the development guide")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or newer is required.")
    try:
        setup(args.android, args.accept_android_sdk_license)
    except (RuntimeError, OSError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
