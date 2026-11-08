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

**Live settings are not established by committing these files.** The owner ran
the administration helper successfully on November 7, 2026. All three active
rulesets, including their bypass actors, were independently read back and matched
the policy at that time. Squash-only merge settings and branch cleanup were also
confirmed. That setup used a separate owner-update ruleset whose admin exception
caused a routine bypass warning when merging.

The current policy replaces that update ruleset with conventional `main` branch
protection, allowing `Joshbomb75` to push/merge and excluding the write-role bot.
This migration has **not been applied or verified live** by this change. Run the
reviewed helper from an owner administration context as described below, then
use `--check` to inspect the resulting settings and later drift.

During initial
setup, the connector could write repository contents but exposed no ruleset or
repository-settings write tool. The CLI authenticated as the bot; an owner CLI
or working owner browser session is needed to apply the administration policy.
The initial repository had no rulesets; the owner completed that application step.

## Intended enforced settings

The complete payloads are in [repository-policy.json](../.github/repository-policy.json).

| Control | Policy |
| --- | --- |
| `main` review | PR, one code-owner approval, stale approval dismissal, approval after the latest reviewable push, resolved conversations, up-to-date required CI |
| Required check | `repository-checks`, bound to GitHub Actions app ID 15368 |
| Branch integrity | Linear history; block deletion and force push; no bypass on the review ruleset |
| Who may update `main` | Conventional branch protection restricts pushes/merges to `Joshbomb75`; no teams or apps are allowed |
| Tags | Only repository admins may create, update, or delete tags |
| Merge settings | Squash only, auto-merge disabled, delete merged branches |
| Actions defaults | Read-only token; Actions cannot approve PRs |
| Security | Secret scanning, push protection, vulnerability alerts |

The conventional push restriction also applies to PR merges. It prevents the
write-role bot from merging an approved PR while allowing an ordinary owner
merge without the old ruleset's routine bypass warning. GitHub still permits
repository admins to push under classic push restrictions; the separate
`questos-main-review` ruleset has no bypass and still requires the PR, approval,
CI, resolved conversations, and branch integrity for everyone. No collaborator
roles or tag restrictions change.

The classic protection's `required_status_checks` and
`required_pull_request_reviews` are `null` because those requirements remain in
the unchanged review ruleset. Rulesets and classic branch protection apply
together. Admins can still change policy through repository administration;
keep admin credentials outside implementation contexts.
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
identity and non-admin credentials and checks the current main's CODEOWNERS and
successful GitHub Actions check. It maintains the two named review/tag rulesets,
creates the conventional owner push restriction, and reads back the effective
branch protection and unchanged rulesets before deleting the exact legacy
`questos-main-owner-updates` ruleset. The legacy payload is kept under
`retired_rulesets` solely to identify the rule that may be removed; it is never
recreated. A replacement write/readback failure leaves the old update gate in
place. Rerunning after successful migration skips the existing replacement.

Apply refuses to overwrite different existing classic branch protection or to
delete a modified/inherited legacy rule. Inspect such conflicts manually. It
preserves unrelated/inherited rulesets and collaborator permissions. It reads
back the configured fields afterward. A failed or unsupported API call is an
error, not a successful setup; writes are not transactional. Inspect the partial
state and rerun only after addressing the error.

For this migration, review and merge the policy/helper PR first (which may need
one last use of the existing bypass), update the owner's checkout to that reviewed
revision, then run `--plan`, `--apply`, and `--check` above. To perform the same
migration through GitHub's UI instead:

1. In **Settings → Branches**, add a classic branch protection rule matching
   exactly `main`. Enable **Restrict who can push to matching branches**, allow
   only `Joshbomb75`, and enable **Do not allow bypassing the above settings**.
   Leave force pushes and deletions disabled. Keep review/check requirements in
   the existing review ruleset.
2. Save and reopen the rule to verify the owner allowance and absence of any bot,
   team, or app allowance. Verify `questos-main-review` is still active with no
   bypass and the same approval/CI requirements.
3. Only then remove `questos-main-owner-updates` from **Settings → Rules →
   Rulesets**. Preserve `questos-main-review` and `questos-owner-tags`. Run the
   reviewed helper's `--check` from the owner administration context.

Afterward, inspect the rulesets and effective branch restriction and verify that
the bot has no bypass or push allowance and retains only its write role.
Use harmless permission checks; do not test by force-pushing, deleting main,
publishing a release, or exposing keys. Verify effective denial before declaring
the implementation access boundary complete.

## Next work

1. Preserve the active rulesets and existing required `repository-checks` gate;
   it depends on both clean native Windows and Linux Quest candidate exports.
2. Save the reusable Codex environment settings using the documented setup recipe.
3. Review the small P1 XR packaging/controller candidate and its dependency/check changes.
4. Owner performs signing and the first headset proof after device preparation.

The owner explicitly deferred removal of the owner GitHub connector for current
work. Continue with the bot for implementation. Full release/credential isolation
remains unproven; it is not a blocker to the setup/development now authorized.

No paid services, release automation, headset changes, or reusable cloud setup
were created by this repository bootstrap. The full retained-release build and
signing handoff belongs to P3. CI results alone never establish device acceptance.
