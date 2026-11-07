#!/usr/bin/env python3
"""Use the project-local Godot toolchain without changing global PATH/settings."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from bootstrap import LOCK, ROOT, TOOLS, sha256


def environment(require_android=False):
    path = TOOLS / "environment.json"
    if not path.is_file():
        raise RuntimeError("Run scripts/setup.ps1 (Windows) or bash scripts/setup.sh (Linux) first.")
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["lock_sha256"] != sha256(LOCK):
        raise RuntimeError("Toolchain lock changed; rerun setup before using this environment.")
    if not Path(config["godot"]).is_file():
        raise RuntimeError("Godot is missing; rerun setup.")
    env = os.environ.copy()
    # Scope application data to this checkout, including in workspace-only sandboxes.
    data = TOOLS / "user-data"
    data.mkdir(exist_ok=True)
    if os.name == "nt":
        env["APPDATA"] = str(data)
        env["LOCALAPPDATA"] = str(data)
    else:
        env["XDG_DATA_HOME"] = str(data)
        env["XDG_CONFIG_HOME"] = str(data / "config")
        env["XDG_CACHE_HOME"] = str(data / "cache")
    android_user = data / "android"
    android_user.mkdir(exist_ok=True)
    env["ANDROID_USER_HOME"] = str(android_user)
    env["ANDROID_EMULATOR_HOME"] = str(android_user)
    if require_android and not all(config.get(key) for key in ("java_home", "android_home")):
        raise RuntimeError("Run setup with --android --accept-android-sdk-license first.")
    if config.get("java_home"):
        env["JAVA_HOME"] = config["java_home"]
        env["PATH"] = str(Path(config["java_home"]) / "bin") + os.pathsep + env.get("PATH", "")
    if config.get("android_home"):
        env["ANDROID_HOME"] = config["android_home"]
        env["ANDROID_SDK_ROOT"] = config["android_home"]
    return config, env


def run(command, env, timeout=180, godot=False):
    result = subprocess.run([str(part) for part in command], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace", timeout=timeout)
    print(result.stdout, end="", flush=True)
    if result.returncode or (godot and any(marker in result.stdout for marker in ("SCRIPT ERROR:", "ERROR:", "Parse Error:"))):
        raise RuntimeError(f"Command failed: {Path(command[0]).name} (exit {result.returncode})")
    return result.stdout


def import_and_smoke(config, env, project):
    base = [config["godot"], "--headless", "--xr-mode", "off", "--path", str(project)]
    run(base + ["--editor", "--import"], env, godot=True)
    run(base + ["--quit-after", "3"], env, godot=True)


def doctor(config, env, android):
    lock = json.loads(LOCK.read_text())
    version = run([config["godot"], "--headless", "--version"], env).strip()
    if not version.startswith(lock["godot_version"] + ".stable."):
        raise RuntimeError("Godot does not match the pinned version.")
    if android:
        suffix = ".exe" if os.name == "nt" else ""
        run([Path(config["java_home"]) / "bin" / ("java" + suffix), "-version"], env)
        sdk = Path(config["android_home"])
        for path, revision in [("build-tools/" + lock["android_build_tools"], lock["android_build_tools"]),
                               ("platform-tools", lock["android_platform_tools"]),
                               (f"platforms/android-{lock['android_platform']}", str(lock["android_platform_revision"]))]:
            properties = (sdk / path / "source.properties").read_text()
            values = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
            if values.get("Pkg.Revision", "").strip() != revision:
                raise RuntimeError(f"Unexpected Android SDK revision in {path}")
        run([sdk / "build-tools" / lock["android_build_tools"] / ("aapt2" + suffix), "version"], env)
    print("Doctor passed" + (" (Android export tools installed)." if android else " (editor installed)."))


def export_android(config, env):
    from inspect_apk import inspect_apk
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    # Do not import from or export with a previous project's .godot cache.
    with tempfile.TemporaryDirectory(prefix="questos-export-") as temporary:
        project = Path(temporary) / "app"
        shutil.copytree(ROOT / "app", project, ignore=shutil.ignore_patterns(".godot"))
        apk = Path(temporary) / "questos-dev-unsigned.apk"
        import_and_smoke(config, env, project)
        run([config["godot"], "--headless", "--xr-mode", "off", "--path", str(project),
             "--export-release", "Android Smoke", str(apk)], env, timeout=300, godot=True)
        report = inspect_apk(apk, config, env)
        destination = build / apk.name
        shutil.copy2(apk, destination)
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    report.update({"source_sha": source_sha, "source_dirty": dirty, "toolchain_lock_sha256": sha256(LOCK),
                   "host": config["host"], "artifact": destination.name,
                   "build_kind": "unsigned Android build smoke test; not an XR headset candidate",
                   "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                   "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                   "github_workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF")})
    (build / "build-manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Inspected unsigned APK: {destination}\nSHA-256: {report['apk_sha256']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "editor", "run", "check", "export-android"])
    parser.add_argument("--android", action="store_true", help="require Android tools for doctor")
    args = parser.parse_args()
    try:
        config, env = environment(args.android or args.command == "export-android")
        if args.command == "doctor":
            doctor(config, env, args.android)
        elif args.command in ("editor", "run"):
            command = [config["godot"], "--path", str(ROOT / "app"), "--xr-mode", "off"]
            if args.command == "editor":
                command.append("--editor")
            return subprocess.call(command, env=env)
        elif args.command == "check":
            import_and_smoke(config, env, ROOT / "app")
        else:
            export_android(config, env)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"Development command failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
