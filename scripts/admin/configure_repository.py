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


class GitHubAPIError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def api(method, path, payload=None):
    command = [
        "gh", "api", "--hostname", "github.com", "--method", method, "--include",
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28", path,
    ]
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True, timeout=60, check=False,
    )
    headers, _, body = result.stdout.replace("\r\n", "\n").partition("\n\n")
    status_line = headers.splitlines()[0].split() if headers else []
    status = int(status_line[1]) if len(status_line) > 1 and status_line[1].isdigit() else None
    if result.returncode or status is None or status >= 400:
        raise GitHubAPIError(f"{method} {path}: {result.stderr.strip() or 'invalid API response'}", status)
    return json.loads(body) if body.strip() else None


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


def read_main_protection(request, base):
    try:
        return request("GET", f"{base}/branches/main/protection")
    except GitHubAPIError as error:
        # Only GitHub's 404 denotes absence; permission/network failures abort.
        if error.status == 404:
            return None
        raise


def protection_matches(expected, actual):
    if not isinstance(actual, dict) or not isinstance(actual.get("restrictions"), dict):
        return False
    restrictions = actual["restrictions"]
    if not all(isinstance(restrictions.get(kind), list) for kind in ("users", "teams", "apps")):
        return False
    normalized = {
        "required_status_checks": actual.get("required_status_checks"),
        "enforce_admins": actual.get("enforce_admins", {}).get("enabled"),
        "required_pull_request_reviews": actual.get("required_pull_request_reviews"),
        "restrictions": {
            kind: [actor.get(field) for actor in restrictions.get(kind, [])]
            for kind, field in [("users", "login"), ("teams", "slug"), ("apps", "slug")]
        },
    }
    return matches(expected, normalized)


def verify_rulesets(policy, request, base):
    rulesets = list_rulesets(request, base)
    for desired in policy["rulesets"]:
        existing = find_owned_ruleset(rulesets, desired, policy["repository"])
        if not existing or not matches(desired, request("GET", f"{base}/rulesets/{existing['id']}")):
            raise RuntimeError(f"Ruleset does not match policy: {desired['name']}")


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
    for desired in policy["rulesets"] + policy["retired_rulesets"]:
        find_owned_ruleset(rulesets, desired, policy["repository"])
    for retired in policy["retired_rulesets"]:
        existing = find_owned_ruleset(rulesets, retired, policy["repository"])
        if existing and not matches(retired, request("GET", f"{base}/rulesets/{existing['id']}")):
            raise RuntimeError(f"Refusing to retire a modified ruleset: {retired['name']}")
    protection = read_main_protection(request, base)
    if protection is not None and not protection_matches(policy["main_branch_protection"], protection):
        raise RuntimeError("Existing main branch protection differs; inspect it manually instead of overwriting it.")
    return rulesets, protection


def apply(policy, request=api):
    rulesets, protection = preflight(policy, request)
    base = f"repos/{policy['repository']}"
    # Preserve unrelated/inherited policy. Only the named legacy gate is retired.
    for desired in policy["rulesets"]:
        existing = find_owned_ruleset(rulesets, desired, policy["repository"])
        if existing:
            path = f"{base}/rulesets/{existing['id']}"
            if not matches(desired, request("GET", path)):
                request("PUT", path, desired)
        else:
            request("POST", f"{base}/rulesets", desired)
    verify_rulesets(policy, request, base)
    if protection is None:
        request("PUT", f"{base}/branches/main/protection", policy["main_branch_protection"])
    # Read back the effective branch protection, not just the write response.
    if not protection_matches(policy["main_branch_protection"], read_main_protection(request, base)):
        raise RuntimeError("Owner push restriction not verified; the legacy update gate was not removed.")
    verify_rulesets(policy, request, base)
    for retired in policy["retired_rulesets"]:
        existing = find_owned_ruleset(rulesets, retired, policy["repository"])
        if existing:
            path = f"{base}/rulesets/{existing['id']}"
            if not matches(retired, request("GET", path)):
                raise RuntimeError(f"Refusing to retire a modified ruleset: {retired['name']}")
            request("DELETE", path)
    request("PATCH", base, policy["settings"])
    request("PUT", f"{base}/actions/permissions/workflow", policy["workflow_permissions"])
    request("PUT", f"{base}/vulnerability-alerts")


def check(policy, request=api):
    base = f"repos/{policy['repository']}"
    failures = []
    repo = request("GET", base)
    if repo.get("default_branch") != "main" or repo.get("visibility") != "public":
        failures.append("expected public repository with default branch main")
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
    if not protection_matches(policy["main_branch_protection"], read_main_protection(request, base)):
        failures.append("main owner push restriction")
    for retired in policy["retired_rulesets"]:
        if find_owned_ruleset(rulesets, retired, policy["repository"]):
            failures.append(f"legacy ruleset still present: {retired['name']}")
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
    print("Configured fields, both active rulesets, and main owner push restriction match the reviewed policy.")
    print("The legacy owner-update bypass ruleset is absent.")
    print("This does not verify every credential, release permission, or device access route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
