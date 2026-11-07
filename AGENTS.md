# QuestOS agent instructions

Read README.md, docs/repository-setup.md, and the relevant sections of the
technical plan before changing the project. The plan is reference material;
the user's current authorization determines the work to execute.

## Scope and access

- Default to ordinary stock-OS application work: Godot, GDScript, OpenXR.
- Use `codexcodemachine` for implementation branches and PRs. Admin access is
  reserved for explicitly authorized setup/administration sessions.
- Do not approve your own work using the owner's account or present an agent
  review as human approval. Owner merges and releases remain separate actions
  unless the user explicitly authorizes a particular administrative bootstrap.
- Do not read or request signing keys, raw device identifiers, account data,
  or retained acceptance records. Never connect to the Windows test station,
  forwarded ADB, or the headset from the development environment.
- Do not run privileged research code, rooting/unlock tools, firmware writers,
  or device reset commands as part of app setup or CI.
- An instruction file is not an access control. Report effective permission
  gaps honestly; do not claim isolation just because these instructions exist.
- The owner explicitly permitted keeping the owner GitHub connector available
  for current project setup/development. Do not block that work on removing it.
  Use the bot for implementation, preserve human PR approval, and report that
  complete credential/release isolation has not been established.

## Changes and validation

- Keep one coherent app change active and keep the owner's review small.
- Make changes on a topic branch and open a PR. Do not push directly to main.
- Workflow, validator, dependency, test, fixture, acceptance-rule, signing-policy,
  and CODEOWNERS changes require explicit owner review.
- Use independent review in a separate read-only context for substantive
  execution, packaging, dependency, measurement, or safeguard changes. Identify
  the reviewed revision and inspect the actual diff and validation evidence.
- Run the checks relevant to the change. Do not invent a coverage target or
  introduce a framework solely to satisfy a check count.
- Keep Actions SHA-pinned and builds free of release secrets. Do not execute
  PR code under `pull_request_target` or privileged follow-up workflows.
- Never label missing or unavailable evidence as a pass. CI is not a headset
  test. Do not infer CPU execution or presented-frame timing from callback gaps.

## Current checks

`python3 -m unittest discover -s tests -v` tests administration, installer, and
package-inspection failure boundaries.
`python3 scripts/admin/configure_repository.py --plan` prints desired settings
without authentication or network access. CI additionally runs actionlint and
clean Quest candidate exports on Windows and Linux. `python3 scripts/dev.py check`
imports, smoke-runs, and checks scene physics. `python3 scripts/dev.py export-android`
builds and inspects an unsigned OpenXR P1 candidate. CI does not pass P1; the owner
must sign and physically test the exact signed APK.
