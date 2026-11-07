# QuestOS

A small Godot/OpenXR learning project for a personally owned Meta Quest 2.
The first deliverable is a performance playground running as an ordinary app
on stock Horizon OS.

**Status:** project-local Windows/Linux tooling, a stationary desktop scene, and
an unsigned Android build smoke test. The smoke APK is a regular Android app,
not an XR headset candidate. XR packaging, controller interaction, standalone
headset launch, and physical acceptance are the next app milestone.

## Start here

- [Technical plan v0.4](docs/QuestOS_Technical_Plan_v0.4.md)
- [Repository administration and remaining setup](docs/repository-setup.md)
- [Development environment requirements](docs/development-environment.md)
- [Contributing](CONTRIBUTING.md) and [agent instructions](AGENTS.md)
- [First app milestone](app/README.md)

## Open the project on Windows

Install Git and Python 3.12 or newer, clone this repository, and run:

```powershell
.\scripts\setup.ps1
py -3 scripts/dev.py editor
```

Native Windows x64 is supported; WSL is optional. If your PowerShell policy
does not allow local scripts, use `py -3 scripts/bootstrap.py` instead.
See the [development guide](docs/development-environment.md) for Android builds,
Linux/WSL commands, disk requirements, and the cloud setup command.

## Checks and export

From the repository root, with Python 3.12 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/dev.py check
```

CI installs the locked tools on fresh Linux and Windows runners, imports and
smoke-runs the scene, exports an unsigned arm64 APK, and checks its package,
SDK levels, permissions, ABI, and lack of signatures. It also runs the unit tests
and workflow lint. The existing required `repository-checks` job depends on
both platform builds; it runs on every PR without path filters. Artifacts expire
after three days. No signing or deployment credentials are used.

Passing CI establishes the tested development/export path, not XR packaging,
physical headset behavior, comfort, or performance acceptance.

## Project boundaries

Implementation work is proposed through PRs. The owner handles merges, retained
release signing, and physical testing. Device identifiers, raw inventory, signing
material, and final acceptance evidence stay outside the development repository.
Root, firmware changes, and privileged on-device experiments are outside the app
workflow. Read-only research notes may accompany app development.

Licensed under the [MIT License](LICENSE).
