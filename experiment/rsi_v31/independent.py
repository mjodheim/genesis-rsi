"""Pinned export and externally signed private-bank replication rehearsal.

Signature validity authenticates a configured key, not independence, identity,
scientific adequacy or L10. Those need external human review.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v31 import bank, campaign, engine, freeze, programs

NAMESPACE = "mira-genesis-l10-review-v1"
ROLES = ("maintainer", "reproducer", "auditor")
AUDIT_CHECKS = ("independent_identity_and_conflicts", "bank_custody_and_prior_commitment",
                "unchanged_lineage_and_evaluator", "complete_tasks_and_negatives",
                "budget_and_archive_integrity", "policy_authority_and_leakage",
                "source_and_task_rights", "claim_scope_and_open_endedness")


def outside_repo(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError("Private execution artifacts must remain outside the public repository")
    return path


def pin():
    value = campaign.check(require_result=True, replay=False)
    frozen = json.loads(freeze.PATH.read_text())
    relative = [path.relative_to(ROOT).as_posix() for path in freeze.inputs()]
    relative.extend(path.relative_to(ROOT).as_posix() for path in (freeze.PATH, campaign.ATTEMPT, campaign.RAW, campaign.VERDICT))
    commit = freeze.git("rev-parse", "HEAD").decode().strip()
    manifest = {}
    for name in sorted(set(relative)):
        raw = (ROOT / name).read_bytes()
        if freeze.git("show", commit + ":" + name) != raw:
            raise ValueError("Export requires committed evidence: " + name)
        manifest[name] = digest_bytes(raw)
    result = {"schema": "mira-genesis-l10-project-pin-v1", "checkout_commit": commit,
              "apparatus_commit": frozen["apparatus_commit"], "freeze_sha256": frozen["freeze_sha256"],
              "policy_sha256": programs.PARENT_SHA256, "manifest": manifest,
              "canonical_verdict_sha256": digest(value), "required_python_version": frozen["python_version"],
              "scope": "UNCHANGED_G7_FINITE_TRANSDUCER_ARCHIVE_REPLICATION_PREPARATION",
              "required_roles": ROLES, "signature_namespace": NAMESPACE,
              "l9_open_ended_passed": False, "l10_independent_passed": False}
    result["project_pin_sha256"] = digest(result)
    return result


def verify_pin(value):
    if (value.get("schema") != "mira-genesis-l10-project-pin-v1" or value.get("project_pin_sha256") != digest(
            {key: item for key, item in value.items() if key != "project_pin_sha256"})
            or value.get("required_roles") not in (list(ROLES), ROLES) or value.get("signature_namespace") != NAMESPACE
            or value.get("policy_sha256") != programs.PARENT_SHA256
            or value.get("l9_open_ended_passed") is not False or value.get("l10_independent_passed") is not False):
        raise ValueError("Altered project pin or claim scope")
    # The pin is supplied out-of-band to the independent operator, not by the actor or task payload.
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["checkout_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Pinned evidence commit is not in this checkout")
    expected = pin()
    if (value["manifest"] != expected["manifest"] or value["freeze_sha256"] != expected["freeze_sha256"]
            or value["canonical_verdict_sha256"] != expected["canonical_verdict_sha256"]
            or value["apparatus_commit"] != expected["apparatus_commit"]
            or value["required_python_version"] != expected["required_python_version"]
            or value["scope"] != expected["scope"]):
        raise ValueError("Project pin does not match the unchanged apparatus and evidence")
    return True


def signature(message, signature_path, allowed_signers, identity):
    if (not identity or identity.casefold().strip() in ("mjodheim", "anthony mets")
            or any(char.isspace() for char in identity) or len(identity) > 128):
        raise ValueError("A separately verified external signer identity is required")
    trusted = Path(allowed_signers).resolve()
    signed = Path(signature_path).resolve()
    if not trusted.is_file() or not signed.is_file():
        raise ValueError("Missing externally configured trust or detached signature")
    run = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(trusted), "-I", identity,
                          "-n", NAMESPACE, "-s", str(signed)], input=message,
                         capture_output=True, timeout=10)
    if run.returncode:
        raise ValueError("External signature verification failed")
    return True


def signed_statement(path, allowed_signers, identity):
    path = Path(path)
    raw = path.read_bytes()
    signature(raw, str(path) + ".sig", allowed_signers, identity)
    value = json.loads(raw)
    if type(value) is not dict:
        raise ValueError("Invalid signed statement")
    return value


def validate_bank_statement(statement, project, raw, tasks, identity):
    required = {"schema", "project_pin_sha256", "bank_bytes_sha256", "task_count", "identity",
                "independently_authored", "committed_before_first_candidate_execution", "custody",
                "domain_description", "conflicts_disclosed"}
    if (set(statement) != required or statement["schema"] != "mira-genesis-l10-bank-commitment-v1"
            or statement["project_pin_sha256"] != project["project_pin_sha256"]
            or statement["bank_bytes_sha256"] != digest_bytes(raw) or type(statement["task_count"]) is not int
            or statement["task_count"] != len(tasks) or statement["identity"] != identity
            or statement["independently_authored"] is not True
            or statement["committed_before_first_candidate_execution"] is not True
            or statement["custody"] != "EXTERNAL_PRIVATE"
            or type(statement["domain_description"]) is not str or not statement["domain_description"].strip()
            or type(statement["conflicts_disclosed"]) is not str):
        raise ValueError("Invalid independently committed bank statement")
    bank.validate_stream(tasks)
    return True


def run_private(project_path, bank_path, statement_path, allowed_signers, identity, output):
    project = json.loads(Path(project_path).read_text())
    verify_pin(project)
    if project["required_python_version"] != sys.version.split()[0]:
        raise ValueError("Use the exact canonical Python runtime for deterministic replication")
    bank_path, output = outside_repo(bank_path), outside_repo(output)
    raw = bank_path.read_bytes()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("External task bank exceeds the fixed payload limit")
    tasks = json.loads(raw)
    if type(tasks) is not list or not 24 <= len(tasks) <= 1024:
        raise ValueError("External bank must contain 24–1024 precommitted tasks")
    statement = signed_statement(outside_repo(statement_path), allowed_signers, identity)
    validate_bank_statement(statement, project, raw, tasks, identity)
    # Exclusive output directory: a failed attempt cannot be silently overwritten/retried.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "ATTEMPT.json", {"status": "STARTED", "project_pin_sha256": project["project_pin_sha256"],
               "bank_bytes_sha256": digest_bytes(raw), "bank_commitment_sha256": digest(statement),
               "trust_file_sha256": digest_bytes(Path(allowed_signers).read_bytes())})
    arms = {}
    for arm in engine.ARMS:
        rows, head = engine.run_stream(tasks, arm, output / (arm + ".jsonl"), project["freeze_sha256"])
        engine.verify_stream(tasks, arm, rows)
        arms[arm] = {"head_sha256": head, "episodes_sha256": digest(rows), "windows": engine.windows(rows),
                     "task_count": len(rows), "evaluations": sum(row["charged_evaluations"] for row in rows)}
    report = {"schema": "mira-genesis-l10-private-replication-report-v1", "status": "COMPLETED",
              "project_pin_sha256": project["project_pin_sha256"], "policy_sha256": programs.PARENT_SHA256,
              "bank_bytes_sha256": digest_bytes(raw), "bank_commitment_sha256": digest(statement),
              "python_version": sys.version.split()[0], "arms": arms,
              "scope": project["scope"], "l9_open_ended_passed": False, "l10_independent_passed": False}
    write_json(output / "REPORT.json", report)
    write_json(output / "ATTEMPT.json", {"status": "COMPLETED", "report_sha256": digest(report)})
    return {"status": "COMPLETED", "report_sha256": digest(report), "task_count": len(tasks),
            "l10_independent_passed": False, "external_identity_scope_and_audit_review_required": True}


def validate_attestations(project, primary_report, reproduction_report, statements, identities):
    if set(identities) != set(ROLES) or len(set(identities.values())) != 3 or set(statements) != {"reproducer", "auditor"}:
        raise ValueError("Three separately trusted external roles are required")
    for identity in identities.values():
        if not identity or identity.casefold().strip() in ("mjodheim", "anthony mets"):
            raise ValueError("Project personnel cannot supply independent roles")
    if primary_report != reproduction_report or primary_report.get("status") != "COMPLETED":
        raise ValueError("Independent reproduction differs from primary evidence")
    if (primary_report.get("project_pin_sha256") != project["project_pin_sha256"]
            or primary_report.get("policy_sha256") != programs.PARENT_SHA256
            or primary_report.get("l9_open_ended_passed") is not False
            or primary_report.get("l10_independent_passed") is not False):
        raise ValueError("Independent evidence substituted the lineage, pin or scope")
    report_sha = digest(primary_report)
    for role in ("reproducer", "auditor"):
        row = statements[role]
        if (row.get("schema") != "mira-genesis-l10-" + role + "-attestation-v1"
                or row.get("project_pin_sha256") != project["project_pin_sha256"]
                or row.get("report_sha256") != report_sha or row.get("identity") != identities[role]
                or row.get("independent_of_project") is not True
                or type(row.get("conflicts_disclosed")) is not str):
            raise ValueError("Invalid external role attestation")
    if statements["reproducer"].get("reran_unchanged_lineage_and_private_bank") is not True:
        raise ValueError("Independent reproduction was not attested")
    checks = statements["auditor"].get("checks")
    if type(checks) is not dict or set(checks) != set(AUDIT_CHECKS) or not all(value is True for value in checks.values()):
        raise ValueError("Incomplete or negative adversarial audit")
    return {"signed_packet_consistent": True, "l10_independent_passed": False,
            "human_review_required": "Verify real identities, conflicts, task independence and adequacy of scope; finite transducer replication cannot establish global RSI."}


def readiness():
    return {"schema": "mira-genesis-l10-readiness-v1", "runner_available": True, "pin_export_available": True,
            "private_bank_signature_required_before_execution": True, "separate_trusted_roles_required": ROLES,
            "independent_task_bank_received": False, "independent_reproduction_received": False,
            "adversarial_audit_received": False, "l9_open_ended_passed": False, "l10_independent_passed": False,
            "scope": "FINITE_TRANSDUCER_REPLICATION_PACKET; broader independently maintained evaluation still required"}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("readiness")
    export = commands.add_parser("export")
    export.add_argument("--output", required=True)
    run = commands.add_parser("run")
    for name in ("project-pin", "private-bank", "bank-statement", "allowed-signers", "identity", "output"):
        run.add_argument("--" + name, required=True)
    verify = commands.add_parser("verify")
    for name in ("project-pin", "primary-report", "reproduction-report", "reproducer-statement", "auditor-statement",
                 "allowed-signers", "maintainer-identity", "reproducer-identity", "auditor-identity"):
        verify.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.action == "readiness":
        result = readiness()
    elif args.action == "export":
        result = pin()
        output = Path(args.output)
        with output.open("x") as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write("\n")
        result = {"project_pin_sha256": result["project_pin_sha256"], "checkout_commit": result["checkout_commit"]}
    elif args.action == "run":
        result = run_private(args.project_pin, args.private_bank, args.bank_statement,
                             args.allowed_signers, args.identity, args.output)
    else:
        project = json.loads(Path(args.project_pin).read_text())
        verify_pin(project)
        identities = {role: getattr(args, role + "_identity") for role in ROLES}
        statements = {role: signed_statement(getattr(args, role + "_statement"), args.allowed_signers, identities[role])
                      for role in ("reproducer", "auditor")}
        result = validate_attestations(project, json.loads(Path(args.primary_report).read_text()),
                                      json.loads(Path(args.reproduction_report).read_text()), statements, identities)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
