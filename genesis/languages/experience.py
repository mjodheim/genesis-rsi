"""G11 module-independent, durable, auditable experience ledger (SQLite).

Experience is stored as *language-neutral observations*, not as serialized
plugin objects or hidden solutions. A removed module cannot retroactively
erase the ledger. Observations are NOT evidence of repaired programs.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from genesis.languages.understanding import SCHEMA as UNDERSTANDING_SCHEMA
from genesis.trust_root import digest_of

SCHEMA = "genesis-language-experience-v1"
_ALLOWED_VERDICTS = {"observed", "candidate_rejected", "full_suite_passed"}


def _fingerprint(report: Mapping[str, Any]) -> dict[str, Any]:
    features = report.get("features") or {}
    kinds = features.get("node_kinds") or []
    # Portable abstraction ignores local names and source text. Record only
    # finite structural concepts and generalized complexity buckets.
    mapped = sorted({str(kind) for kind in kinds if isinstance(kind, str) and len(kind) <= 64})
    return {
        "node_kinds": mapped[:64],
        "has_branch": bool(features.get("has_branch")),
        "has_call": bool(features.get("has_call")),
        "multiple_branches": int(features.get("branch_count", 0)) > 1,
        "multiple_calls": int(features.get("call_count", 0)) > 1,
    }


def _validated_report(report: Mapping[str, Any]) -> None:
    if report.get("schema") != UNDERSTANDING_SCHEMA:
        raise ValueError("unsupported understanding report schema")
    unsigned = {k: v for k, v in report.items() if k != "analysis_digest"}
    if report.get("analysis_digest") != digest_of(unsigned):
        raise ValueError("understanding digest mismatch")


class ExperienceLedger:
    """Persistent insights that remain available after a language module goes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS g11_events(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                previous_digest TEXT NOT NULL,
                event_digest TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(
        self,
        report: Mapping[str, Any],
        *,
        operator: str = "none",
        verdict: str = "observed",
        evaluator_evidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a use/outcome, without storing code or requiring the module.

        'full_suite_passed' may only be labelled when an evaluator supplies
        frozen and full-suite evidence IDs. The ledger preserves this *claim*
        for independent verification; it does not itself run the evaluator.
        """
        _validated_report(report)
        if verdict not in _ALLOWED_VERDICTS:
            raise ValueError("invalid verdict")
        evidence = dict(evaluator_evidence or {})
        if verdict == "full_suite_passed":
            required = ("blind_freeze_digest", "evaluator_digest", "full_suite_result_digest")
            if any(not isinstance(evidence.get(k), str) or not evidence[k] for k in required):
                raise ValueError("full-suite success requires auditable evaluator evidence")
        elif verdict == "observed" and evidence:
            raise ValueError("an observation must not claim evaluator evidence")
        if len(operator) > 128 or not operator:
            raise ValueError("invalid operator")
        body: dict[str, Any] = {
            "schema": SCHEMA,
            "language": report["language"],
            "module_id_at_observation": report["module_id"],
            "fidelity_at_observation": report["fidelity"],
            "source_digest": report["source_digest"],
            "analysis_digest": report["analysis_digest"],
            "portable_pattern": _fingerprint(report),
            "operator": operator,
            "verdict": verdict,
            "evaluator_evidence_digest": digest_of(evidence) if evidence else None,
            "claim_status": ("reported_not_independently_verified"
                             if verdict == "full_suite_passed" else "observation_only"),
        }
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute(
                "SELECT event_digest FROM g11_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous = last[0] if last else ""
            event = {**body, "previous_digest": previous}
            event_digest = digest_of(event)
            db.execute(
                "INSERT INTO g11_events(previous_digest,event_digest,payload_json) VALUES(?,?,?)",
                (previous, event_digest, json.dumps(event, sort_keys=True, separators=(",", ":"))),
            )
        return {**event, "event_digest": event_digest}

    def events(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT previous_digest,event_digest,payload_json FROM g11_events ORDER BY sequence"
            ).fetchall()
        previous = ""
        events: list[dict[str, Any]] = []
        for prev, digest, raw in rows:
            record = json.loads(raw)
            if prev != previous or record.get("previous_digest") != prev or digest_of(record) != digest:
                raise ValueError("experience ledger integrity verification failed")
            previous = digest
            events.append({**record, "event_digest": digest})
        return events

    def knowledge_summary(self) -> dict[str, Any]:
        """Portable observations and *reported* success, with no false promotion."""
        records = self.events()
        patterns: Counter[str] = Counter()
        operators: Counter[str] = Counter()
        verified_claims: Counter[str] = Counter()
        for record in records:
            signature = digest_of(record["portable_pattern"])
            patterns[signature] += 1
            operators[record["operator"]] += 1
            if record["verdict"] == "full_suite_passed":
                verified_claims[signature] += 1
        body = {
            "schema": "genesis-portable-experience-summary-v1",
            "observation_count": len(records),
            "portable_pattern_counts": dict(sorted(patterns.items())),
            "operator_usage_counts": dict(sorted(operators.items())),
            "reported_full_suite_success_counts": dict(sorted(verified_claims.items())),
            "independently_verified_full_suite_successes": 0,
            "last_event_digest": records[-1]["event_digest"] if records else "",
            "depends_on_installed_modules": False,
        }
        return {**body, "summary_digest": digest_of(body)}
