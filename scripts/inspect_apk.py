"""Validate the development package; does not establish device behavior or origin."""

from pathlib import Path
import re
import subprocess
import zipfile

from bootstrap import sha256

PACKAGE = "org.johnsondev.questos.dev"


def inspect_apk(apk, config, env):
    lock = config["toolchain"]
    suffix = ".exe" if config["host"] == "windows" else ""
    tool = Path(config["android_home"]) / "build-tools" / lock["android_build_tools"] / ("aapt2" + suffix)

    def dump(*args):
        result = subprocess.run([str(tool), "dump", *args], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                                encoding="utf-8", errors="replace")
        if result.returncode:
            raise RuntimeError(f"APK inspection failed: {result.stderr}")
        return result.stdout

    badging = dump("badging", str(apk))
    manifest = dump("xmltree", str(apk), "--file", "AndroidManifest.xml")
    if f"package: name='{PACKAGE}' versionCode='1' versionName='0.1.0-dev'" not in badging:
        raise RuntimeError("Unexpected APK package or version identity.")
    if not re.search(r"(?:minSdkVersion|sdkVersion):'24'", badging) or "targetSdkVersion:'36'" not in badging:
        raise RuntimeError("Unexpected Android SDK compatibility.")
    if "native-code: 'arm64-v8a'" not in badging:
        raise RuntimeError("Expected arm64-only APK.")
    if "application-debuggable" in badging:
        raise RuntimeError("Expected a non-debuggable release export.")
    permissions = sorted(set(re.findall(r"uses-permission(?:-sdk-\d+)?: name='([^']+)'", badging)))
    if permissions:
        raise RuntimeError("Unexpected APK permissions: " + ", ".join(permissions))
    if "android.intent.category.LAUNCHER" not in manifest:
        raise RuntimeError("Android smoke-test launcher activity is missing.")
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        abis = sorted({name.split("/")[1] for name in names if name.startswith("lib/") and name.endswith(".so")})
        if abis != ["arm64-v8a"]:
            raise RuntimeError(f"Unexpected native-library ABIs: {abis}")
        if b"--xr_mode_regular" not in archive.read("assets/_cl_"):
            raise RuntimeError("Expected regular Android mode for the build smoke test.")
        if any(re.match(r"META-INF/.*\.(SF|RSA|DSA|EC)$", name, re.I) for name in names):
            raise RuntimeError("Development APK unexpectedly contains signing metadata.")
        # APK v2/v3 signatures reside immediately before the ZIP central directory.
        with apk.open("rb") as stream:
            stream.seek(max(0, archive.start_dir - 16))
            if stream.read(16) == b"APK Sig Block 42":
                raise RuntimeError("Development APK unexpectedly contains an APK signing block.")
    return {"apk_sha256": sha256(apk), "package": PACKAGE, "version_code": 1,
            "version_name": "0.1.0-dev", "minimum_sdk": 24, "target_sdk": 36,
            "abis": abis, "permissions": permissions, "xr_headset_candidate": False,
            "signing": "unsigned", "size_bytes": apk.stat().st_size}
