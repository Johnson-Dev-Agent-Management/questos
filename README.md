# QuestOS

A small Godot/OpenXR learning project for a personally owned Meta Quest 2.
The first deliverable is a performance playground running as an ordinary app
on stock Horizon OS.

**Status:** repository foundation. No Android export or headset-tested build yet.
The first app milestone is a stationary scene, controller interaction, standalone
launch, and normal exit. Workloads and validated measurements come afterward.

## Start here

- [Technical plan v0.4](docs/QuestOS_Technical_Plan_v0.4.md)
- [Repository administration and remaining setup](docs/repository-setup.md)
- [Development environment requirements](docs/development-environment.md)
- [Contributing](CONTRIBUTING.md) and [agent instructions](AGENTS.md)
- [First app milestone](app/README.md)

## Checks

From the repository root, with Python 3.12 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/admin/configure_repository.py --plan
```

The `repository-checks` CI job also lints GitHub Actions workflows with a
checksum-pinned actionlint binary. It runs on every PR without path filters,
uses a read-only GitHub token, and has no signing or deployment credentials.
Passing it does not establish Android buildability or physical XR behavior.

## Project boundaries

Implementation work is proposed through PRs. The owner handles merges, retained
release signing, and physical testing. Device identifiers, raw inventory, signing
material, and final acceptance evidence stay outside the development repository.
Root, firmware changes, and privileged on-device experiments are outside the app
workflow. Read-only research notes may accompany app development.

Licensed under the [MIT License](LICENSE).
