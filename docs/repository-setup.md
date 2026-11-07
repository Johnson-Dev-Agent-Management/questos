# Repository setup

Repository: `Johnson-Dev-Agent-Management/questos` (public).
Owner: `Joshbomb75` (admin). Implementation identity: `codexcodemachine` (write).
These roles were verified during setup on November 7, 2026.

## What the bootstrap provides

- The technical plan, a small contribution workflow, owner CODEOWNERS, and PR template.
- A `repository-checks` CI job with a read-only token, SHA-pinned checkout,
  checksum-pinned actionlint, bounded runtime, and no release credentials.
- Monthly GitHub Actions dependency-update PRs, limited to two open PRs.
- A reviewed policy and owner-run administration helper for the settings below.

**Live settings are not established by committing these files.** During initial
setup, the connector could write repository contents but exposed no ruleset or
repository-settings write tool. The CLI authenticated as the bot; an owner CLI
or working owner browser session is needed to apply the administration policy.
The initial repository had no rulesets. Run `--check` after applying the policy
to establish the current state, rather than treating this historical note as a
live assertion.

## Intended enforced settings

The complete payloads are in [repository-policy.json](../.github/repository-policy.json).

| Control | Policy |
| --- | --- |
| `main` review | PR, one code-owner approval, stale approval dismissal, approval after the latest reviewable push, resolved conversations, up-to-date required CI |
| Required check | `repository-checks`, bound to GitHub Actions app ID 15368 |
| Branch integrity | Linear history; block deletion and force push; no bypass on the review ruleset |
| Who may update `main` | Separate update restriction; only repository admins may bypass that restriction |
| Tags | Only repository admins may create, update, or delete tags |
| Merge settings | Squash only, auto-merge disabled, delete merged branches |
| Actions defaults | Read-only token; Actions cannot approve PRs |
| Security | Secret scanning, push protection, vulnerability alerts |

The separate update restriction prevents the write-role bot from merging even
an approved PR. The admin exception on that restriction does **not** bypass
the separate PR/check requirements. Admins can still change policy through
repository administration; keep admin credentials outside implementation contexts.
CODEOWNERS must exist on `main` before enforcement. An owner-authored PR cannot
receive its required approval from the same owner: normal implementation PRs
should be authored by the bot. The initial bootstrap is a one-time setup action.

Tag restrictions do not revoke all release rights. A write-role account may
still edit releases associated with existing tags or perform other content
operations. Full release separation remains open until upstream permissions
are reduced to a suitable role/fork workflow or an equivalent enforceable
boundary is established. This helper deliberately preserves the roles the
owner configured; it does not claim to solve that gap.

## Apply from an owner administration context

First review the bootstrap, put it on `main`, and wait for its `repository-checks`
run to pass. Inspect a pinned, reviewed copy of the script and policy before
running them with owner credentials. Do not execute an unreviewed PR's scripts
in an owner-authenticated environment.

With Python 3.12+ and GitHub CLI installed, authenticate GitHub CLI as
`Joshbomb75` using GitHub's normal sign-in flow. Keep credentials out of chat.
An existing `GH_TOKEN` or `GITHUB_TOKEN` environment variable can override a
stored CLI login; `gh api user --jq .login` verifies the identity actually used.

From the reviewed repository root:

```sh
gh api user --jq .login
python3 scripts/admin/configure_repository.py --plan
python3 scripts/admin/configure_repository.py --apply
python3 scripts/admin/configure_repository.py --check
```

On Windows, `py -3` may be used in place of `python3`.

The default/`--plan` mode has no network access or writes. Apply refuses the bot
identity and non-admin credentials, checks the current main's CODEOWNERS and
successful GitHub Actions check, then creates or updates only the three named
rulesets. It preserves unrelated/inherited rulesets and collaborator permissions.
It reads back the configured fields afterward. A failed or unsupported API call
is an error, not a successful setup; writes are not transactional. Inspect the
partial state and rerun only after addressing the error.

Afterward, inspect the rulesets as the bot and verify that the bot has no bypass.
Use harmless permission checks; do not test by force-pushing, deleting main,
publishing a release, or exposing keys. Verify effective denial before declaring
the implementation access boundary complete.

## Next work

1. Apply and verify the administration policy with owner-capable access.
2. Remove owner-authorized connections from the future implementation context;
   resolve the bot's remaining release capability and check device isolation.
3. Pin the Godot/Android toolchain and establish one clean export/inspection.
4. Add the demonstrated Android export job as a required check.
5. Owner performs signing and the first headset proof after device preparation.

No paid services, release automation, headset changes, or reusable cloud setup
were created by this repository bootstrap. The full retained-release build and
signing handoff belongs to P3. CI results alone never establish device acceptance.
