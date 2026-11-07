#!/usr/bin/env python3
"""Preview, apply, or check QuestOS's owner-reviewed repository configuration.

Run only a reviewed copy with the owner's gh authentication. This is not a CI job.
It does not create credentials, modify collaborators, merge PRs, or publish builds.
"""

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".github" / "repository-policy.json"


def api(method, path, payload=None):
    command = [
        "gh", "api", "--hostname", "github.com", "--method", method,
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28", path,
    ]
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True, timeout=60, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{method} {path}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def matches(expected, actual):
    """Compare intended fields while ignoring server-managed fields and list order."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        remaining = list(actual)
        for item in expected:
            for index, candidate in enumerate(remaining):
                if matches(item, candidate):
                    remaining.pop(index)
                    break
            else:
                return False
        return True
    return type(expected) is type(actual) and expected == actual


def list_rulesets(request, base):
    rulesets = []
    page = 1
    while True:
        batch = request("GET", f"{base}/rulesets?includes_parents=true&per_page=100&page={page}")
        rulesets.extend(batch)
        if len(batch) < 100:
            return rulesets
        page += 1


def find_owned_ruleset(rulesets, desired, repository):
    found = [item for item in rulesets if item["name"] == desired["name"]]
    if len(found) > 1:
        raise RuntimeError(f"Ambiguous ruleset name: {desired['name']}")
    if found and (
        found[0].get("source_type") != "Repository"
        or found[0].get("source") != repository
    ):
        raise RuntimeError(f"Refusing to replace inherited ruleset: {desired['name']}")
    return found[0] if found else None


def preflight(policy, request):
    """Finish every prerequisite read before performing any administrative write."""
    base = f"repos/{policy['repository']}"
    actor = request("GET", "user")["login"]
    if actor.casefold() != policy["administrator"].casefold():
        raise RuntimeError(f"Refusing writes as {actor}; use {policy['administrator']}.")
    repo = request("GET", base)
    if not repo.get("permissions", {}).get("admin"):
        raise RuntimeError("The active GitHub credential lacks repository administration access.")
    if repo.get("default_branch") != "main" or repo.get("visibility") != "public":
        raise RuntimeError("Expected the existing public repository with default branch main.")
    branch = request("GET", f"{base}/branches/main")
    sha = branch["commit"]["sha"]
    contents = request("GET", f"{base}/contents/.github/CODEOWNERS?ref={sha}")
    owners = base64.b64decode(contents["content"]).decode("utf-8")
    if f"* @{policy['administrator']}" not in owners.splitlines():
        raise RuntimeError("Merge the owner-reviewed CODEOWNERS bootstrap before applying rules.")
    errors = request("GET", f"{base}/codeowners/errors?ref={sha}")
    if errors.get("errors"):
        raise RuntimeError("GitHub reports CODEOWNERS errors; fix these before applying rules.")
    checks = request("GET", f"{base}/commits/{sha}/check-runs?filter=latest&per_page=100")
    if not any(
        check["name"] == "repository-checks"
        and check.get("conclusion") == "success"
        and check.get("app", {}).get("id") == 15368
        and check.get("app", {}).get("slug") == "github-actions"
        for check in checks["check_runs"]
    ):
        raise RuntimeError("Current main must have a successful repository-checks run from GitHub Actions.")
    rulesets = list_rulesets(request, base)
    for desired in policy["rulesets"]:
        find_owned_ruleset(rulesets, desired, policy["repository"])
    return rulesets


def apply(policy, request=api):
    rulesets = preflight(policy, request)
    base = f"repos/{policy['repository']}"
    # No deletion of unrelated rulesets or replacement of inherited policy.
    for desired in policy["rulesets"]:
        existing = find_owned_ruleset(rulesets, desired, policy["repository"])
        if existing:
            path = f"{base}/rulesets/{existing['id']}"
            if not matches(desired, request("GET", path)):
                request("PUT", path, desired)
        else:
            request("POST", f"{base}/rulesets", desired)
    request("PATCH", base, policy["settings"])
    request("PUT", f"{base}/actions/permissions/workflow", policy["workflow_permissions"])
    request("PUT", f"{base}/vulnerability-alerts")


def check(policy, request=api):
    base = f"repos/{policy['repository']}"
    failures = []
    repo = request("GET", base)
    if not matches(policy["settings"], repo):
        failures.append("repository settings/security scanning")
    permissions = request("GET", f"{base}/actions/permissions/workflow")
    if not matches(policy["workflow_permissions"], permissions):
        failures.append("default workflow token permissions")
    rulesets = list_rulesets(request, base)
    for desired in policy["rulesets"]:
        existing = find_owned_ruleset(rulesets, desired, policy["repository"])
        if not existing or not matches(desired, request("GET", f"{base}/rulesets/{existing['id']}")):
            failures.append(desired["name"])
    request("GET", f"{base}/vulnerability-alerts")  # 204 if enabled; 404 fails.
    if failures:
        raise RuntimeError("Configuration differs: " + ", ".join(failures))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true", help="print desired policy; no network or writes (default)")
    modes.add_argument("--apply", action="store_true", help="apply with the owner identity and verify afterward")
    modes.add_argument("--check", action="store_true", help="verify live configuration without writes")
    args = parser.parse_args(argv)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if not args.apply and not args.check:
        print(json.dumps(policy, indent=2))
        return 0
    try:
        if args.apply:
            apply(policy)
        check(policy)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Configuration not verified: {error}", file=sys.stderr)
        if args.apply:
            print("Writes are not transactional. Inspect live settings before retrying; no rollback was attempted.", file=sys.stderr)
        return 1
    print("Configured fields and all three named rulesets match the reviewed policy.")
    print("This does not verify every credential, release permission, or device access route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
