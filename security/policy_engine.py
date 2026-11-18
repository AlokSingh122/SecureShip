"""SecureShip policy engine.

Turns raw scanner output (Trivy, Gitleaks, Checkov JSON) into a pass/fail decision
using security/policy.yaml.

Design rules:
  * Fail closed. A report that was requested but is missing or unparsable is an error (exit 2),
    never a silent pass.
  * Never echo secrets. Gitleaks findings are reduced to rule id, file and line.
  * Exceptions are explicit, owned and time-boxed. Expired exceptions fail the gate.

Exit codes: 0 = pass, 1 = policy violations, 2 = engine/input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

SEVERITIES = ["UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
REQUIRED_EXCEPTION_FIELDS = ("id", "tool", "finding_id", "reason", "owner", "expires")


class PolicyError(Exception):
    """Raised for invalid policy files or unusable scanner reports."""


@dataclass
class Finding:
    tool: str  # trivy | gitleaks | checkov
    source: str  # trivy-fs | trivy-image | gitleaks | checkov
    finding_id: str
    severity: str
    target: str  # package@version, file:line, or terraform resource
    title: str = ""
    fixed_version: str | None = None


# --------------------------------------------------------------------------- loading

def load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PolicyError(f"cannot read policy file {path}: {exc}") from exc
    if (
        not isinstance(policy, dict)
        or isinstance(policy.get("version"), bool)
        or policy.get("version") != 1
    ):
        raise PolicyError("policy file must be a mapping with 'version: 1'")
    policy.setdefault("exceptions", [])
    if not isinstance(policy["exceptions"], list):
        raise PolicyError("'exceptions' must be a list")
    for exc_entry in policy["exceptions"]:
        if not isinstance(exc_entry, dict):
            raise PolicyError("each exception must be a mapping")
        missing = [f for f in REQUIRED_EXCEPTION_FIELDS if not exc_entry.get(f)]
        if missing:
            raise PolicyError(
                f"exception {exc_entry.get('id', '?')} is missing required fields: {missing}"
            )
        if any(not isinstance(exc_entry[field], str) for field in REQUIRED_EXCEPTION_FIELDS[:-1]):
            raise PolicyError(f"exception {exc_entry['id']}: required fields must be strings")
        if "target" in exc_entry and not isinstance(exc_entry["target"], str):
            raise PolicyError(f"exception {exc_entry['id']}: 'target' must be a string")
        exp = exc_entry["expires"]
        if isinstance(exp, str):
            try:
                exc_entry["expires"] = date.fromisoformat(exp)
            except ValueError as err:
                raise PolicyError(f"exception {exc_entry['id']}: bad date {exp!r}") from err
        elif isinstance(exp, datetime) or not isinstance(exp, date):
            raise PolicyError(f"exception {exc_entry['id']}: 'expires' must be a date")
    for name in ("trivy", "gitleaks", "checkov"):
        if name in policy and not isinstance(policy[name], dict):
            raise PolicyError(f"'{name}' policy section must be a mapping")
    fail_on_severity = policy.get("trivy", {}).get("fail_on_severity", [])
    if not isinstance(fail_on_severity, list) or not all(
        isinstance(severity, str) for severity in fail_on_severity
    ):
        raise PolicyError("'trivy.fail_on_severity' must be a list of severity names")
    if any(severity.upper() not in SEVERITIES for severity in fail_on_severity):
        raise PolicyError("'trivy.fail_on_severity' contains an unknown severity")
    for name in ("gitleaks", "checkov"):
        setting = policy.get(name, {}).get("fail_on_any", True)
        if not isinstance(setting, bool):
            raise PolicyError(f"'{name}.fail_on_any' must be a boolean")
    return policy


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"{label} report not found: {path} (failing closed)") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"{label} report unreadable: {path}: {exc}") from exc


# --------------------------------------------------------------------------- parsers

def parse_trivy(data: Any, source: str) -> list[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("Results"), list):
        raise PolicyError(f"{source}: unexpected Trivy JSON structure")
    findings: list[Finding] = []
    for result in data["Results"]:
        if not isinstance(result, dict):
            raise PolicyError(f"{source}: each Trivy result must be a mapping")
        vulnerabilities = result.get("Vulnerabilities", [])
        if vulnerabilities is None:
            vulnerabilities = []
        if not isinstance(vulnerabilities, list):
            raise PolicyError(f"{source}: Trivy Vulnerabilities must be a list or null")
        for vuln in vulnerabilities:
            if not isinstance(vuln, dict):
                raise PolicyError(f"{source}: each Trivy vulnerability must be a mapping")
            for key in ("VulnerabilityID", "Severity", "PkgName", "InstalledVersion", "Title", "FixedVersion"):
                if vuln.get(key) is not None and not isinstance(vuln[key], str):
                    raise PolicyError(f"{source}: Trivy vulnerability field {key} must be a string")
            severity = str(vuln.get("Severity", "UNKNOWN")).upper()
            if severity not in SEVERITIES:
                severity = "UNKNOWN"
            findings.append(
                Finding(
                    tool="trivy",
                    source=source,
                    finding_id=vuln.get("VulnerabilityID", "UNKNOWN-ID"),
                    severity=severity,
                    target=f"{vuln.get('PkgName', '?')}@{vuln.get('InstalledVersion', '?')}",
                    title=vuln.get("Title", ""),
                    fixed_version=vuln.get("FixedVersion") or None,
                )
            )
    return findings


def parse_gitleaks(data: Any) -> list[Finding]:
    if not isinstance(data, list):
        raise PolicyError("gitleaks: expected a JSON list of findings")
    # The 'Secret'/'Match' fields are intentionally never read or copied.
    findings: list[Finding] = []
    for item in data:
        if not isinstance(item, dict):
            raise PolicyError("gitleaks: each finding must be a mapping")
        for key in ("RuleID", "File", "Description"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise PolicyError(f"gitleaks: finding field {key} must be a string")
        start_line = item.get("StartLine", "?")
        if not isinstance(start_line, (str, int)):
            raise PolicyError("gitleaks: finding field StartLine must be a string or integer")
        findings.append(
            Finding(
                tool="gitleaks",
                source="gitleaks",
                finding_id=item.get("RuleID", "unknown-rule"),
                severity="HIGH",
                target=f"{item.get('File', '?')}:{start_line}",
                title=item.get("Description", ""),
            )
        )
    return findings


def parse_checkov(data: Any) -> list[Finding]:
    reports = data if isinstance(data, list) else [data]
    findings: list[Finding] = []
    for report in reports:
        if not isinstance(report, dict):
            raise PolicyError("checkov: unexpected JSON structure")
        results = report.get("results")
        if not isinstance(results, dict):
            raise PolicyError("checkov: results must be a mapping")
        failed_checks = results.get("failed_checks")
        if not isinstance(failed_checks, list):
            raise PolicyError("checkov: failed_checks must be a list")
        for check in failed_checks:
            if not isinstance(check, dict):
                raise PolicyError("checkov: each failed check must be a mapping")
            for key in ("check_id", "resource", "check_name", "severity"):
                if check.get(key) is not None and not isinstance(check[key], str):
                    raise PolicyError(f"checkov: finding field {key} must be a string")
            findings.append(
                Finding(
                    tool="checkov",
                    source="checkov",
                    finding_id=check.get("check_id", "UNKNOWN"),
                    severity=str(check.get("severity") or "HIGH").upper(),
                    target=check.get("resource") or "?",
                    title=check.get("check_name", ""),
                )
            )
    return findings


# --------------------------------------------------------------------------- evaluation

def _is_blocking(finding: Finding, policy: dict[str, Any]) -> tuple[bool, bool]:
    """Return (blocking, ignored_as_unfixed)."""
    if finding.tool == "trivy":
        if finding.severity == "UNKNOWN" or finding.severity not in SEVERITIES:
            return True, False
        cfg = policy.get("trivy", {})
        if cfg.get("ignore_unfixed", False) and not finding.fixed_version:
            return False, True
        return finding.severity in {s.upper() for s in cfg.get("fail_on_severity", [])}, False
    if finding.tool == "gitleaks":
        return bool(policy.get("gitleaks", {}).get("fail_on_any", True)), False
    if finding.tool == "checkov":
        return bool(policy.get("checkov", {}).get("fail_on_any", True)), False
    return True, False  # unknown tool: fail closed


def _matching_exception(finding: Finding, exceptions: list[dict[str, Any]], today: date):
    for exc in exceptions:
        if exc["tool"] != finding.tool or exc["finding_id"] != finding.finding_id:
            continue
        target = exc.get("target")
        if target and target not in finding.target:
            continue
        if exc["expires"] >= today:
            return exc
    return None


def evaluate(findings: list[Finding], policy: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    exceptions = policy.get("exceptions", [])
    violations: list[dict[str, Any]] = []
    waived: list[dict[str, Any]] = []
    unfixed_ignored = 0

    for finding in findings:
        blocking, unfixed = _is_blocking(finding, policy)
        if unfixed:
            unfixed_ignored += 1
        if not blocking:
            continue
        exc = _matching_exception(finding, exceptions, today)
        if exc:
            waived.append({**asdict(finding), "exception_id": exc["id"], "expires": exc["expires"].isoformat()})
        else:
            violations.append(asdict(finding))

    # Expired exceptions are violations in their own right.
    for exc in exceptions:
        if exc["expires"] < today:
            violations.append(
                {
                    "tool": "policy",
                    "source": "policy.yaml",
                    "finding_id": exc["id"],
                    "severity": "HIGH",
                    "target": f"{exc['tool']}:{exc['finding_id']}",
                    "title": f"Exception expired on {exc['expires'].isoformat()}; renew with review or remove it",
                    "fixed_version": None,
                }
            )

    by_severity = Counter(f.severity for f in findings)
    return {
        "passed": not violations,
        "evaluated_on": today.isoformat(),
        "violations": violations,
        "waived": waived,
        "counts": {
            "total_findings": len(findings),
            "violations": len(violations),
            "waived": len(waived),
            "unfixed_ignored": unfixed_ignored,
            "by_severity": {s: by_severity.get(s, 0) for s in SEVERITIES},
            "by_source": dict(Counter(f.source for f in findings)),
        },
    }


# --------------------------------------------------------------------------- CLI

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="security.policy_engine", description="Evaluate scan reports against policy.yaml")
    p.add_argument("--policy", required=True, type=Path)
    p.add_argument("--trivy-fs", type=Path)
    p.add_argument("--trivy-image", type=Path)
    p.add_argument("--gitleaks", type=Path)
    p.add_argument("--checkov", type=Path)
    p.add_argument("--output", type=Path, help="write the decision JSON here")
    p.add_argument("--today", type=date.fromisoformat, help="override today's date (testing)")
    return p


def _print_summary(decision: dict[str, Any]) -> None:
    counts = decision["counts"]
    print("=" * 60)
    print("SECURESHIP POLICY DECISION:", "PASS" if decision["passed"] else "FAIL")
    print("=" * 60)
    print(f"findings={counts['total_findings']} violations={counts['violations']} "
          f"waived={counts['waived']} unfixed_ignored={counts['unfixed_ignored']}")
    print("by severity:", {k: v for k, v in counts["by_severity"].items() if v})
    for v in decision["violations"]:
        fix = f" (fix: {v['fixed_version']})" if v.get("fixed_version") else ""
        print(f"  [BLOCK] {v['source']:<12} {v['severity']:<8} {v['finding_id']} {v['target']}{fix}")
    for w in decision["waived"]:
        print(f"  [WAIVED] {w['source']:<11} {w['finding_id']} {w['target']} via {w['exception_id']}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        policy = load_policy(args.policy)
        findings: list[Finding] = []
        if args.trivy_fs:
            findings += parse_trivy(_load_json(args.trivy_fs, "trivy-fs"), "trivy-fs")
        if args.trivy_image:
            findings += parse_trivy(_load_json(args.trivy_image, "trivy-image"), "trivy-image")
        if args.gitleaks:
            findings += parse_gitleaks(_load_json(args.gitleaks, "gitleaks"))
        if args.checkov:
            findings += parse_checkov(_load_json(args.checkov, "checkov"))
        if not any([args.trivy_fs, args.trivy_image, args.gitleaks, args.checkov]):
            raise PolicyError("no scan reports supplied; refusing to pass an empty evaluation")
        decision = evaluate(findings, policy, args.today)
    except PolicyError as exc:
        print(f"POLICY ENGINE ERROR: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    _print_summary(decision)
    return 0 if decision["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
