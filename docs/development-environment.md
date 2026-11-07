# Development environment

Use native Windows x64 or Linux x64, including WSL2. WSL is optional. Git and
Python 3.12+ are prerequisites; Android Studio, Docker, a global Java install,
administrator privileges, and a headset are not required.

The shared Python installer has PowerShell and Bash entry points. It verifies
archive checksums and installs a self-contained Godot editor under `.tools/`.
It does not change machine PATH, registry settings, or an existing Godot/SDK
installation. Development helpers keep application data inside `.tools/user-data`.
Use one setup/export at a time per checkout; do not rerun setup while its editor
is open. Keep separate Windows and WSL checkouts because their executables and
absolute paths differ.

## Windows: inspect and edit the project

Install Git and Python 3.12 or newer from their official installers, then:

```powershell
git clone https://github.com/Johnson-Dev-Agent-Management/questos.git
cd questos
.\scripts\setup.ps1
py -3 scripts/dev.py doctor
py -3 scripts/dev.py editor
```

`py -3 scripts/dev.py run` opens the desktop scene; closing its window exits.
The editor/run helpers disable XR on desktop, so no PC VR runtime is needed.
Run `py -3 scripts/dev.py check` for a headless import and short scene smoke test.

If local PowerShell script execution is blocked, run
`py -3 scripts/bootstrap.py` instead. There is no need to weaken the machine's
execution policy. If Python was installed without the `py` launcher, replace
`py -3` with `python` after checking that `python --version` is at least 3.12.

## Linux and WSL

With Git and Python 3.12+ installed, from the checkout:

```sh
bash scripts/setup.sh
python3 scripts/dev.py doctor
python3 scripts/dev.py editor
```

The GUI needs a desktop/display, such as the cloud Desktop panel or WSLg.
Headless `check` and `export-android` work without a display. The tested Linux
baseline is Ubuntu 24.04; a minimal distribution may need its standard Godot
runtime libraries. No system packages are installed automatically.

## Quest 2 candidate export (either operating system)

Review the [Android SDK terms](https://developer.android.com/studio/terms).
The explicit acceptance flag enables the additional SDK installation.

Windows:

```powershell
.\scripts\setup.ps1 --android --accept-android-sdk-license
py -3 scripts/dev.py doctor --android
py -3 scripts/dev.py export-android
```

Linux/WSL:

```sh
bash scripts/setup.sh --android --accept-android-sdk-license
python3 scripts/dev.py doctor --android
python3 scripts/dev.py export-android
```

Allow roughly 2.5 GB of downloads and 7 GB of free space for the full setup. The
editor-only setup downloads about 80 MB. Archives are cached in `.tools/downloads`;
subsequent setup reuses verified installations. A checksum mismatch fails rather
than accepting changed bytes. An interrupted extraction is repaired on retry.
Deleting `.tools/` removes the installed project toolchain and local editor data.
It does not remove your system tools.

The export helper copies the project to a fresh temporary directory, imports
resources, smoke-runs the scene, and exports without any existing `.godot` cache.
It inspects the resulting package before placing it in
`build/questos-p1-unsigned.apk`, with `build/build-manifest.json` containing the
digest, source revision/dirty state sampled before the build, copied project
snapshot digest, toolchain-lock digest, host, and CI identifiers
when applicable. CI exports the tested checkout, which is normally GitHub's PR
merge revision on pull-request runs. A changed HEAD/dirty state during export
fails before publication. Local dirty builds are identified as such; their
snapshot digest identifies the copied project without claiming it matches HEAD.

This is an **unsigned XR headset candidate**, not a physical P1 pass. The fresh
Godot Gradle template uses Gradle 8.11.1, AGP 8.6.1, Kotlin 2.1.21, Khronos loader
1.1.54, and the existing API 36/build-tools 36.0.0 setup. Runtime declarations are
minSdk 29 / targetSdk 32 for the Quest 2 sideload candidate; compiling against
API 36 does not require API 36 on the headset. The device's actual OS/API and
runtime compatibility remain unknown until the owner tests it. No store release
or compatibility with every Horizon version is claimed.

The export adds Quest 2 metadata, immersive launch categories, runtime broker
queries, and only the two OpenXR permissions. Inspection verifies these on the
actual APK, along with the exact arm64 loader bytes, ELF architecture, release
identity, absence of signing, and the OpenXR command line. Gradle dependencies
use committed version locks and strict SHA-256 verification (including the
Windows aapt2 artifact). Missing/changed locks fail; export never refreshes them.
The NDK is unnecessary: the template ships prebuilt native libraries, whose
symbols are kept instead of downloading a compiler to strip them again.

Gradle caches remain under `.tools/gradle-user-home`; each project/build tree is
fresh. Java receives the inherited HTTP(S) proxy settings. Managed Linux uses its
OS Java trust store when an explicit certificate bundle is configured; native
Windows uses Temurin trust. `QUESTOS_JAVA_TRUSTSTORE` can select a trusted local
store. TLS verification stays enabled. Do not put authenticated proxy credentials
into Java options/build logs. Dependency refresh is a separately reviewed change:
generate Gradle locks/checksums in a disposable build, inspect new coordinates
and official source artifacts, include both host classifiers, update lockfile
hashes, and run both clean platform jobs.

See the [Windows signing/install/test handoff](p1-headset-handoff.md). Nothing in
these development helpers installs an APK or connects to a device.

## Codex Cloud configuration

The current cloud workspace can run this recipe. To make a reusable project
environment in Codex environment settings, use:

| Setting | Value |
| --- | --- |
| Repository | `Johnson-Dev-Agent-Management/questos` |
| Branch | `main` after the toolchain PR is reviewed and merged |
| Runtime | Linux x64, Git, Python 3.12+, standard Godot runtime libraries |
| Setup command, from repo root | `bash scripts/cloud-setup.sh` |
| Verification/maintenance command | `python3 scripts/dev.py doctor --android` |
| Secrets | None required for installing/building; bot-scoped GitHub access for PR work |
| Setup network hosts | `github.com`, `api.github.com`, `release-assets.githubusercontent.com`, `dl.google.com`, `downloads.gradle.org`, `repo.maven.apache.org`, `repo1.maven.org`, `plugins.gradle.org`, `plugins-artifacts.gradle.org` |
| Private networking | No VPN, forwarded ADB, or connection to the owner's test station |

`cloud-setup.sh` includes the explicit Android SDK acceptance flag and runs
`doctor --android`. Setup is repeatable in a fresh checkout; publishing a reusable
Codex environment configuration is a separate environment-settings action.
This chat exposes no tool to save/publish that configuration, so running the
recipe here must not be described as publishing an environment snapshot.

The owner explicitly permitted the owner GitHub connector to remain available
for current work. Use the bot for implementation branches/PRs; retain owner
review, merge, and signing responsibilities. The bot still has upstream write
access. These are acknowledged limits to credential/release isolation, not
claims that rulesets remove all release capabilities. No release keys, headset
access, or Windows remote execution is needed for development.

See [toolchain provenance](toolchain-provenance.md) for exact selections and
source evidence. Run `python3 -m unittest discover -s tests -v` for local tests.
The required CI gate also tests fresh Linux and native Windows exports in paths
with spaces and preserves their unsigned artifacts for three days.
