# QuestOS

A small Godot/OpenXR learning project for a personally owned Meta Quest 2.
The first deliverable is a performance playground running as an ordinary app
on stock Horizon OS.

**Status:** off-device Quest 2 P1 candidate: a stationary scene, Touch-controller
ray selection to toggle a cube's color, and a selectable Exit control. Clean
Gradle/OpenXR exports are inspected on Linux and native Windows. Owner signing
and physical headset launch/input/exit tests are still required; P1 is not passed.

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
smoke-runs the scene, exports an unsigned arm64 Quest candidate, and checks its XR metadata/loader, package,
SDK levels, permissions, ABI, and lack of signatures. It also runs the unit tests
and workflow lint. The existing required `repository-checks` job depends on
both platform builds; it runs on every PR without path filters. Artifacts expire
after three days. No signing or deployment credentials are used.

Passing CI establishes the tested development/export path and inspected XR
packaging. Physical headset behavior, comfort, and performance remain unverified.
See the [Windows P1 handoff](docs/p1-headset-handoff.md).

## Project boundaries

Implementation work is proposed through PRs. The owner handles merges, retained
release signing, and physical testing. Device identifiers, raw inventory, signing
material, and final acceptance evidence stay outside the development repository.
Root, firmware changes, and privileged on-device experiments are outside the app
workflow. Read-only research notes may accompany app development.

Licensed under the [MIT License](LICENSE).
