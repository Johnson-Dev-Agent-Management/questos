#!/usr/bin/env python3
"""Use the project-local Godot toolchain without changing global PATH/settings."""

import argparse
import hashlib
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
    lock_bytes = LOCK.read_bytes()
    if config["lock_sha256"] != hashlib.sha256(lock_bytes).hexdigest():
        raise RuntimeError("Toolchain lock changed; rerun setup before using this environment.")
    config["toolchain"] = json.loads(lock_bytes)
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
    run(base + ["--script", ROOT / "tests/godot/test_interaction.gd"], env, godot=True)


def doctor(config, env, android):
    lock = config["toolchain"]
    version = run([config["godot"], "--headless", "--version"], env).strip()
    if not version.startswith(lock["godot_version"] + ".stable."):
        raise RuntimeError("Godot does not match the pinned version.")
    if android:
        suffix = ".exe" if os.name == "nt" else ""
        java_version = run([Path(config["java_home"]) / "bin" / ("java" + suffix), "-version"], env)
        if "build " + lock["java_version"] not in java_version:
            raise RuntimeError("Java does not match the pinned build.")
        if sha256(TOOLS / "downloads" / lock["assets"]["gradle"]["file"]) != lock["assets"]["gradle"]["sha256"]:
            raise RuntimeError("Gradle distribution checksum mismatch; rerun setup.")
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


def source_identity():
    return {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())}


def project_digest(project):
    digest = hashlib.sha256()
    for path in sorted(p for p in project.rglob("*") if p.is_file()):
        digest.update(path.relative_to(project).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path).encode("ascii") + b"\n")
    return digest.hexdigest()


def export_android(config, env):
    from inspect_apk import inspect_apk
    from android_build import prepare_gradle, gradle_environment
    env = gradle_environment(env)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    identity = source_identity()
    # Do not import from or export with a previous project's .godot cache.
    with tempfile.TemporaryDirectory(prefix="questos-export-") as temporary:
        project = Path(temporary) / "app"
        shutil.copytree(ROOT / "app", project, ignore=shutil.ignore_patterns(".godot"))
        snapshot_digest = project_digest(project)
        apk = Path(temporary) / "questos-p1-unsigned.apk"
        import_and_smoke(config, env, project)
        prepare_gradle(project, config)
        run([config["godot"], "--headless", "--xr-mode", "off", "--path", str(project),
             "--export-release", "Quest 2 Candidate", str(apk)], env, timeout=900, godot=True)
        report = inspect_apk(apk, config, env)
        if source_identity() != identity:
            raise RuntimeError("Source revision or dirty state changed during export; rerun from a stable checkout.")
        destination = build / apk.name
        shutil.copy2(apk, destination)
    report.update({**identity, "project_snapshot_sha256": snapshot_digest, "toolchain_lock_sha256": config["lock_sha256"],
                   "host": config["host"], "artifact": destination.name,
                   "build_kind": "unsigned Quest 2 P1 candidate; physical validation pending",
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
