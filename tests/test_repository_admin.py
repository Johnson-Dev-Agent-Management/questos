"""Exercise administrative failure boundaries without live GitHub writes."""

import base64
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_admin", ROOT / "scripts/admin/configure_repository.py")
admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admin)
POLICY = json.loads((ROOT / ".github/repository-policy.json").read_text())
BASE = "repos/" + POLICY["repository"]


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.actor = "Joshbomb75"
        self.is_admin = True
        self.checks = [{"name": "repository-checks", "conclusion": "success",
                        "app": {"id": 15368, "slug": "github-actions"}}]
        self.rulesets = []
        self.codeowners_errors = []

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method != "GET":
            return {}
        if path == "user":
            return {"login": self.actor}
        if path == BASE:
            return {"permissions": {"admin": self.is_admin}, "default_branch": "main", "visibility": "public"}
        if path.endswith("/branches/main"):
            return {"commit": {"sha": "a" * 40}}
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
        admin.apply(POLICY, github)
        writes = [(method, path) for method, path, _ in github.calls if method != "GET"]
        self.assertFalse(any("rulesets" in path for _, path in writes))
        self.assertFalse(any(method == "DELETE" for method, _ in writes))

    def test_extra_bypass_actor_does_not_pass_verification(self):
        desired = POLICY["rulesets"][0]
        actual = copy.deepcopy(desired)
        actual["bypass_actors"] = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
        self.assertFalse(admin.matches(desired, actual))

    def test_main_review_cannot_be_bypassed_and_owner_update_gate_is_separate(self):
        review, updates, tags = POLICY["rulesets"]
        self.assertEqual(review["bypass_actors"], [])
        types = {rule["type"] for rule in review["rules"]}
        self.assertTrue({"pull_request", "required_status_checks", "deletion", "non_fast_forward"} <= types)
        self.assertEqual(updates["rules"], [{"type": "update"}])
        for rule in [updates, tags]:
            self.assertEqual(rule["bypass_actors"], [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}])


if __name__ == "__main__":
    unittest.main()
