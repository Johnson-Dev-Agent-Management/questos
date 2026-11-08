"""Exercise administrative failure boundaries without live GitHub writes."""

import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_admin", ROOT / "scripts/admin/configure_repository.py")
admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admin)
POLICY = json.loads((ROOT / ".github/repository-policy.json").read_text())
BASE = "repos/" + POLICY["repository"]


def protection_response(payload):
    return {
        "enforce_admins": {"enabled": payload["enforce_admins"]},
        "restrictions": {
            kind: [{field: name} for name in payload["restrictions"][kind]]
            for kind, field in [("users", "login"), ("teams", "slug"), ("apps", "slug")]
        },
        **{key: payload[key] for key in ["required_status_checks", "required_pull_request_reviews"]},
    }


def stored_rules(rules):
    return [dict(copy.deepcopy(rule), id=index + 1, source_type="Repository", source=POLICY["repository"])
            for index, rule in enumerate(rules)]


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.actor = "Joshbomb75"
        self.is_admin = True
        self.checks = [{"name": "repository-checks", "conclusion": "success",
                        "app": {"id": 15368, "slug": "github-actions"}}]
        self.rulesets = []
        self.codeowners_errors = []
        self.protection = None

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "POST" and path.endswith("/rulesets"):
            self.rulesets.append(dict(copy.deepcopy(payload), id=len(self.rulesets) + 1,
                                      source_type="Repository", source=POLICY["repository"]))
            return self.rulesets[-1]
        if method == "DELETE" and "/rulesets/" in path:
            self.rulesets = [rule for rule in self.rulesets if str(rule["id"]) != path.rsplit("/", 1)[1]]
            return None
        if method == "PUT" and path.endswith("/branches/main/protection"):
            self.protection = protection_response(payload)
            return copy.deepcopy(self.protection)
        if method != "GET":
            return {}
        if path == "user":
            return {"login": self.actor}
        if path == BASE:
            return {"permissions": {"admin": self.is_admin}, "default_branch": "main", "visibility": "public"}
        if path.endswith("/branches/main"):
            return {"commit": {"sha": "a" * 40}}
        if path.endswith("/branches/main/protection"):
            if self.protection is None:
                raise admin.GitHubAPIError("Branch not protected", 404)
            return copy.deepcopy(self.protection)
        if "/contents/.github/CODEOWNERS?" in path:
            return {"content": base64.b64encode(b"* @Joshbomb75\n").decode()}
        if "/codeowners/errors?" in path:
            return {"errors": self.codeowners_errors}
        if "/check-runs?" in path:
            return {"check_runs": self.checks}
        if "/rulesets?" in path:
            return self.rulesets
        if "/rulesets/" in path:
            return next(rule for rule in self.rulesets if str(rule["id"]) == path.rsplit("/", 1)[1])
        raise AssertionError(f"Unexpected request: {method} {path}")


class AdministrationTests(unittest.TestCase):
    def assert_no_writes(self, github):
        self.assertTrue(all(method == "GET" for method, _, _ in github.calls))

    def test_plan_never_invokes_network(self):
        with patch.object(admin, "api", side_effect=AssertionError("network")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(admin.main(["--plan"]), 0)

    def test_wrong_identity_and_non_admin_are_rejected_before_writes(self):
        for actor, is_admin in [("codexcodemachine", True), ("Joshbomb75", False)]:
            with self.subTest(actor=actor, is_admin=is_admin):
                github = FakeGitHub()
                github.actor, github.is_admin = actor, is_admin
                with self.assertRaises(RuntimeError):
                    admin.apply(POLICY, github)
                self.assert_no_writes(github)

    def test_missing_failed_and_spoofed_checks_cannot_enable_protection(self):
        for checks in [[], [{"name": "repository-checks", "conclusion": "failure", "app": {"id": 15368}}],
                       [{"name": "repository-checks", "conclusion": "success", "app": {"id": 42}}]]:
            with self.subTest(checks=checks):
                github = FakeGitHub()
                github.checks = checks
                with self.assertRaises(RuntimeError):
                    admin.apply(POLICY, github)
                self.assert_no_writes(github)

    def test_invalid_codeowners_blocks_all_writes(self):
        github = FakeGitHub()
        github.codeowners_errors = [{"message": "Unknown owner"}]
        with self.assertRaises(RuntimeError):
            admin.apply(POLICY, github)
        self.assert_no_writes(github)

    def test_inherited_name_collision_is_never_overwritten(self):
        github = FakeGitHub()
        github.rulesets = [{"name": POLICY["rulesets"][0]["name"], "id": 10, "source_type": "Organization", "source": "org"}]
        with self.assertRaises(RuntimeError):
            admin.apply(POLICY, github)
        self.assert_no_writes(github)

    def test_repeat_apply_preserves_unrelated_rules_and_skips_identical_rules(self):
        github = FakeGitHub()
        github.rulesets = [dict(copy.deepcopy(rule), id=index + 1, source_type="Repository", source=POLICY["repository"])
                           for index, rule in enumerate(POLICY["rulesets"])]
        github.rulesets.append({"name": "unrelated", "id": 99, "source_type": "Repository", "source": POLICY["repository"]})
        github.protection = protection_response(POLICY["main_branch_protection"])
        admin.apply(POLICY, github)
        writes = [(method, path) for method, path, _ in github.calls if method != "GET"]
        self.assertFalse(any("rulesets" in path for _, path in writes))
        self.assertFalse(any(method == "DELETE" for method, _ in writes))
        self.assertFalse(any("/protection" in path for _, path in writes))

    def test_extra_bypass_actor_does_not_pass_verification(self):
        desired = POLICY["rulesets"][0]
        actual = copy.deepcopy(desired)
        actual["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        self.assertFalse(admin.matches(desired, actual))

    def test_check_detects_default_branch_and_visibility_drift_without_writes(self):
        for branch, visibility in [("main", "public"), ("unprotected", "public"), ("main", "private")]:
            with self.subTest(branch=branch, visibility=visibility):
                github = FakeGitHub()
                github.rulesets = [dict(copy.deepcopy(rule), id=index + 1, source_type="Repository", source=POLICY["repository"])
                                   for index, rule in enumerate(POLICY["rulesets"])]
                github.protection = protection_response(POLICY["main_branch_protection"])

                def request(method, path, payload=None):
                    if path == BASE:
                        return dict(copy.deepcopy(POLICY["settings"]), default_branch=branch, visibility=visibility)
                    if path.endswith("/actions/permissions/workflow"):
                        return POLICY["workflow_permissions"]
                    if path.endswith("/vulnerability-alerts"):
                        return None
                    return github(method, path, payload)

                if branch == "main" and visibility == "public":
                    admin.check(POLICY, request)
                else:
                    with self.assertRaisesRegex(RuntimeError, "default branch main"):
                        admin.check(POLICY, request)
                self.assert_no_writes(github)

    def test_main_review_cannot_be_bypassed_and_owner_push_gate_is_separate(self):
        review, tags = POLICY["rulesets"]
        self.assertEqual(review["bypass_actors"], [])
        types = {rule["type"] for rule in review["rules"]}
        self.assertTrue({"pull_request", "required_status_checks", "deletion", "non_fast_forward"} <= types)
        self.assertEqual(POLICY["main_branch_protection"]["restrictions"],
                         {"users": ["Joshbomb75"], "teams": [], "apps": []})
        self.assertEqual(tags["bypass_actors"], [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}])

    def test_migration_verifies_replacement_before_removing_legacy_gate(self):
        github = FakeGitHub()
        github.rulesets = stored_rules(POLICY["rulesets"] + POLICY["retired_rulesets"])
        admin.apply(POLICY, github)
        writes = [(method, path) for method, path, _ in github.calls if method != "GET"]
        self.assertLess(writes.index(("PUT", BASE + "/branches/main/protection")),
                        writes.index(("DELETE", BASE + "/rulesets/3")))
        deletion = next(i for i, (method, _, _) in enumerate(github.calls) if method == "DELETE")
        creation = next(i for i, (method, path, _) in enumerate(github.calls)
                        if method == "PUT" and path.endswith("/protection"))
        between = [(method, path) for method, path, _ in github.calls[creation + 1:deletion]]
        self.assertIn(("GET", BASE + "/branches/main/protection"), between)
        self.assertIn(("GET", BASE + "/rulesets/1"), between)
        self.assertEqual([rule["name"] for rule in github.rulesets], [rule["name"] for rule in POLICY["rulesets"]])
        # A second application never recreates or re-deletes the retired ruleset.
        github.calls.clear()
        admin.apply(POLICY, github)
        self.assertFalse(any(method != "GET" and ("rulesets" in path or "/protection" in path)
                             for method, path, _ in github.calls))

    def test_unverified_or_failed_replacement_keeps_legacy_gate(self):
        for failure in ["write_error", "missing", "extra_user", "extra_team", "extra_app", "review_drift"]:
            with self.subTest(failure=failure):
                github = FakeGitHub()
                github.rulesets = stored_rules(POLICY["rulesets"] + POLICY["retired_rulesets"])

                def request(method, path, payload=None):
                    if method == "PUT" and path.endswith("/protection"):
                        if failure == "write_error":
                            raise admin.GitHubAPIError("Forbidden", 403)
                        result = github(method, path, payload)
                        if failure == "missing":
                            github.protection = None
                        elif failure.startswith("extra_"):
                            kind, field = {"extra_user": ("users", "login"), "extra_team": ("teams", "slug"),
                                           "extra_app": ("apps", "slug")}[failure]
                            github.protection["restrictions"][kind].append({field: "unexpected"})
                        elif failure == "review_drift":
                            github.rulesets[0]["enforcement"] = "disabled"
                        return result
                    return github(method, path, payload)

                with self.assertRaises(RuntimeError):
                    admin.apply(POLICY, request)
                self.assertFalse(any(method == "DELETE" for method, _, _ in github.calls))
                self.assertTrue(any(rule["name"] == "questos-main-owner-updates" for rule in github.rulesets))

    def test_existing_different_classic_protection_is_not_overwritten(self):
        github = FakeGitHub()
        github.protection = protection_response(POLICY["main_branch_protection"])
        github.protection["required_status_checks"] = {"strict": True, "contexts": ["other-check"]}
        with self.assertRaisesRegex(RuntimeError, "Existing main branch protection differs"):
            admin.apply(POLICY, github)
        self.assert_no_writes(github)

    def test_modified_or_inherited_legacy_rule_cannot_be_retired(self):
        for change in [{"enforcement": "disabled"}, {"source_type": "Organization", "source": "org"}]:
            github = FakeGitHub()
            github.rulesets = stored_rules(POLICY["retired_rulesets"])
            github.rulesets[0].update(change)
            with self.assertRaises(RuntimeError):
                admin.apply(POLICY, github)
            self.assert_no_writes(github)

    def test_protection_read_permission_and_network_errors_abort_before_writes(self):
        for status in [None, 401, 403, 429, 500]:
            github = FakeGitHub()

            def request(method, path, payload=None):
                if path.endswith("/protection"):
                    raise admin.GitHubAPIError("unavailable", status)
                return github(method, path, payload)

            with self.assertRaises(admin.GitHubAPIError):
                admin.apply(POLICY, request)
            self.assert_no_writes(github)

    def test_check_requires_replacement_and_absence_of_legacy_rule(self):
        for failure in ["missing", "extra_actor", "legacy"]:
            github = FakeGitHub()
            github.rulesets = stored_rules(POLICY["rulesets"])
            github.protection = protection_response(POLICY["main_branch_protection"])
            if failure == "missing":
                github.protection = None
            elif failure == "extra_actor":
                github.protection["restrictions"]["users"].append({"login": "codexcodemachine"})
            else:
                github.rulesets = stored_rules(POLICY["rulesets"] + POLICY["retired_rulesets"])

            def request(method, path, payload=None):
                if path == BASE:
                    return dict(copy.deepcopy(POLICY["settings"]), default_branch="main", visibility="public")
                if path.endswith("/actions/permissions/workflow"):
                    return POLICY["workflow_permissions"]
                if path.endswith("/vulnerability-alerts"):
                    return None
                return github(method, path, payload)

            with self.assertRaises(RuntimeError):
                admin.check(POLICY, request)
            self.assert_no_writes(github)

    def test_api_parses_github_status_without_treating_other_failures_as_absence(self):
        for output, returncode, status in [
            ('HTTP/2.0 404 Not Found\r\nContent-Type: application/json\r\n\r\n{"message":"Branch not protected"}', 1, 404),
            ('HTTP/2.0 403 Forbidden\n\n{"message":"Forbidden"}', 1, 403),
            ("", 1, None),
        ]:
            with patch.object(admin.subprocess, "run", return_value=subprocess.CompletedProcess([], returncode, output, "error")):
                with self.assertRaises(admin.GitHubAPIError) as raised:
                    admin.api("GET", BASE + "/branches/main/protection")
                self.assertEqual(raised.exception.status, status)
        for output, expected in [('HTTP/2.0 200 OK\n\n{"ok":true}', {"ok": True}),
                                 ('HTTP/2.0 204 No Content\r\n\r\n', None)]:
            with patch.object(admin.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")):
                self.assertEqual(admin.api("GET", BASE), expected)


if __name__ == "__main__":
    unittest.main()
