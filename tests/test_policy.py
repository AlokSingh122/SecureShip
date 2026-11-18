import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from security import policy_engine as engine

TODAY = date(2026, 11, 17)

POLICY = {
    "version": 1,
    "trivy": {"fail_on_severity": ["CRITICAL", "HIGH"], "ignore_unfixed": True},
    "gitleaks": {"fail_on_any": True},
    "checkov": {"fail_on_any": True},
    "exceptions": [],
}


def trivy_report(*vulns):
    return {"Results": [{"Target": "requirements.txt", "Vulnerabilities": list(vulns)}]}


def vuln(vid="CVE-2024-0001", sev="HIGH", pkg="libx", ver="1.0", fixed="1.1"):
    return {"VulnerabilityID": vid, "Severity": sev, "PkgName": pkg, "InstalledVersion": ver, "FixedVersion": fixed}


def exception(**over):
    base = {
        "id": "EXC-T", "tool": "checkov", "finding_id": "CKV_TEST_1", "target": "aws_instance.app",
        "reason": "r", "owner": "o", "expires": date(2027, 1, 1),
    }
    base.update(over)
    return base


class TrivyPolicyTests(unittest.TestCase):
    def run_eval(self, *vulns, policy=POLICY):
        findings = engine.parse_trivy(trivy_report(*vulns), "trivy-fs")
        return engine.evaluate(findings, policy, TODAY)

    def test_critical_with_fix_blocks(self):
        d = self.run_eval(vuln(sev="CRITICAL"))
        self.assertFalse(d["passed"])
        self.assertEqual(d["counts"]["violations"], 1)

    def test_high_blocks(self):
        self.assertFalse(self.run_eval(vuln(sev="HIGH"))["passed"])

    def test_medium_and_low_pass_but_are_counted(self):
        d = self.run_eval(vuln(sev="MEDIUM"), vuln(vid="CVE-2", sev="LOW"))
        self.assertTrue(d["passed"])
        self.assertEqual(d["counts"]["total_findings"], 2)

    def test_unknown_severity_blocks(self):
        for severity in ("UNKNOWN", "NEGLIGIBLE"):
            with self.subTest(severity=severity):
                decision = self.run_eval(vuln(sev=severity))
                self.assertFalse(decision["passed"])
                self.assertEqual(decision["violations"][0]["severity"], "UNKNOWN")

    def test_unfixed_is_ignored_but_reported(self):
        d = self.run_eval(vuln(sev="CRITICAL", fixed=None))
        self.assertTrue(d["passed"])
        self.assertEqual(d["counts"]["unfixed_ignored"], 1)

    def test_unfixed_blocks_when_not_ignored(self):
        strict = {**POLICY, "trivy": {"fail_on_severity": ["CRITICAL"], "ignore_unfixed": False}}
        self.assertFalse(self.run_eval(vuln(sev="CRITICAL", fixed=None), policy=strict)["passed"])

    def test_clean_report_passes(self):
        findings = engine.parse_trivy({"Results": [{"Target": "x", "Vulnerabilities": None}]}, "trivy-fs")
        self.assertTrue(engine.evaluate(findings, POLICY, TODAY)["passed"])

    def test_malformed_trivy_structures_are_rejected(self):
        for data in ({}, {"Results": {}}, {"Results": ["not a result"]},
                     {"Results": [{"Vulnerabilities": "not a list"}]},
                     {"Results": [{"Vulnerabilities": [None]}]}):
            with self.subTest(data=data), self.assertRaises(engine.PolicyError):
                engine.parse_trivy(data, "trivy-fs")


SENTINEL = "-".join(["leak", "canary", "value"])  # assembled so this file holds no secret-like literal


class GitleaksTests(unittest.TestCase):
    def test_any_secret_blocks_and_value_is_never_copied(self):
        data = [{"RuleID": "generic-api-key", "File": "app/x.py", "StartLine": 3,
                 "Secret": SENTINEL, "Match": "key=" + SENTINEL, "Description": "key"}]
        findings = engine.parse_gitleaks(data)
        d = engine.evaluate(findings, POLICY, TODAY)
        self.assertFalse(d["passed"])
        self.assertNotIn(SENTINEL, json.dumps(d))

    def test_empty_report_passes(self):
        self.assertEqual(engine.parse_gitleaks([]), [])

    def test_malformed_gitleaks_report_is_rejected(self):
        for data in (None, {}, [None], [{"StartLine": []}]):
            with self.subTest(data=data), self.assertRaises(engine.PolicyError):
                engine.parse_gitleaks(data)


class CheckovTests(unittest.TestCase):
    def report(self, *checks):
        return {"results": {"failed_checks": list(checks)}}

    def check(self, cid="CKV_AWS_24", res="aws_security_group.bad"):
        return {"check_id": cid, "check_name": "n", "resource": res}

    def test_failed_check_blocks(self):
        d = engine.evaluate(engine.parse_checkov(self.report(self.check())), POLICY, TODAY)
        self.assertFalse(d["passed"])

    def test_list_of_framework_reports_is_supported(self):
        data = [self.report(self.check()), self.report()]
        self.assertEqual(len(engine.parse_checkov(data)), 1)

    def test_malformed_checkov_report_is_rejected(self):
        for data in ({}, {"results": []}, self.report(None),
                     {"results": {"failed_checks": {}}}):
            with self.subTest(data=data), self.assertRaises(engine.PolicyError):
                engine.parse_checkov(data)

    def test_active_exception_waives_matching_finding_only(self):
        policy = {**POLICY, "exceptions": [exception()]}
        waived = engine.evaluate(
            engine.parse_checkov(self.report(self.check("CKV_TEST_1", "aws_instance.app"))), policy, TODAY)
        self.assertTrue(waived["passed"])
        self.assertEqual(waived["counts"]["waived"], 1)
        other = engine.evaluate(
            engine.parse_checkov(self.report(self.check("CKV_TEST_1", "aws_instance.other"))), policy, TODAY)
        self.assertFalse(other["passed"])

    def test_expired_exception_fails_the_gate_even_with_no_findings(self):
        policy = {**POLICY, "exceptions": [exception(expires=date(2026, 1, 1))]}
        d = engine.evaluate([], policy, TODAY)
        self.assertFalse(d["passed"])
        self.assertEqual(d["violations"][0]["tool"], "policy")

    def test_exception_for_other_tool_does_not_waive(self):
        policy = {**POLICY, "exceptions": [exception(tool="trivy")]}
        d = engine.evaluate(engine.parse_checkov(self.report(self.check("CKV_TEST_1", "aws_instance.app"))),
                            policy, TODAY)
        self.assertFalse(d["passed"])


class PolicyLoadingTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return Path(f.name)

    def test_exception_missing_owner_is_rejected(self):
        p = self.write("version: 1\nexceptions:\n  - {id: E1, tool: checkov, finding_id: X, reason: r, expires: 2027-01-01}\n")
        with self.assertRaises(engine.PolicyError):
            engine.load_policy(p)

    def test_wrong_version_is_rejected(self):
        with self.assertRaises(engine.PolicyError):
            engine.load_policy(self.write("version: 2\n"))

    def test_malformed_policy_sections_are_rejected(self):
        for text in ("version: 1\nexceptions: {}\n",
                     "version: 1\nexceptions: [null]\n",
                     "version: 1\ntrivy: []\n",
                     "version: 1\ntrivy: {fail_on_severity: CRITICAL}\n"):
            with self.subTest(text=text), self.assertRaises(engine.PolicyError):
                engine.load_policy(self.write(text))

    def test_shipped_policy_is_valid(self):
        policy = engine.load_policy(Path(__file__).resolve().parents[1] / "security" / "policy.yaml")
        self.assertEqual(policy["version"], 1)
        self.assertIsInstance(policy["exceptions"], list)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.policy = self.tmp / "policy.yaml"
        self.policy.write_text("version: 1\ntrivy: {fail_on_severity: [CRITICAL], ignore_unfixed: true}\n")

    def test_missing_report_fails_closed_with_exit_2(self):
        rc = engine.main(["--policy", str(self.policy), "--trivy-fs", str(self.tmp / "nope.json")])
        self.assertEqual(rc, 2)

    def test_no_reports_supplied_is_an_error(self):
        self.assertEqual(engine.main(["--policy", str(self.policy)]), 2)

    def test_corrupt_report_fails_closed(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json")
        self.assertEqual(engine.main(["--policy", str(self.policy), "--trivy-fs", str(bad)]), 2)

    def test_violation_returns_1_and_writes_decision(self):
        rep = self.tmp / "t.json"
        rep.write_text(json.dumps(trivy_report(vuln(sev="CRITICAL"))))
        out = self.tmp / "out" / "decision.json"
        rc = engine.main(["--policy", str(self.policy), "--trivy-fs", str(rep), "--output", str(out)])
        self.assertEqual(rc, 1)
        self.assertFalse(json.loads(out.read_text())["passed"])

    def test_clean_report_returns_0(self):
        rep = self.tmp / "t.json"
        rep.write_text(json.dumps(trivy_report(vuln(sev="LOW"))))
        self.assertEqual(engine.main(["--policy", str(self.policy), "--trivy-fs", str(rep)]), 0)


if __name__ == "__main__":
    unittest.main()
