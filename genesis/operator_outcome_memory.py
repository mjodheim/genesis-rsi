"""Post-evaluation *training-only* memory of repair operator outcomes.

Scientific boundary:
- A fresh independent evaluation is performed with a frozen model/policy.
- Only AFTER its result is published may explicitly released cases become
  training observations; those cases can never count as fresh again.
- The memory stores compact behavioral classifications, not human solutions.
- No module automatically promotes itself or changes candidate priority.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from genesis.trust_root import digest_of

_SCHEMA = "genesis-repair-operator-training-outcomes-v1"
_OPERATORS = re.compile(r"^[a-z][a-z0-9_:.-]{1,127}$")
_OUTCOMES = {"compile_failed", "public_trigger_failed", "full_suite_failed", "full_suite_passed"}


class OperatorOutcomeMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS training_attempts(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  previous_digest TEXT NOT NULL,
                  event_digest TEXT NOT NULL UNIQUE,
                  payload_json TEXT NOT NULL
                )
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(
        self,
        *,
        project: str,
        case_digest: str,
        candidate_sha256: str,
        operators: list[str],
        public_failure_symptom: str,
        outcome: str,
        freeze_digest: str,
        independent_evaluator_digest: str,
        role: str,
    ) -> dict[str, Any]:
        """Only trusted caller may explicitly submit released training cases.

        This method cannot by itself verify the evaluator cryptographically;
        outcomes are retained claims, never independent scientific proof.
        """
        if role != "released_training":
            raise ValueError("only explicitly released training cases may enter memory")
        if outcome not in _OUTCOMES:
            raise ValueError("invalid outcome")
        if not (1 <= len(operators) <= 8 and all(_OPERATORS.fullmatch(o) for o in operators)):
            raise ValueError("operators must be recognizable portable identifiers")
        for name, val in {
            "case_digest": case_digest,
            "candidate_sha256": candidate_sha256,
            "freeze_digest": freeze_digest,
            "independent_evaluator_digest": independent_evaluator_digest,
        }.items():
            if not isinstance(val, str) or not re.fullmatch(r"[0-9a-f]{64}", val):
                raise ValueError(f"invalid {name}")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}", project):
            raise ValueError("invalid project identity")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,79}", public_failure_symptom):
            raise ValueError("invalid symptom")
        body = {
            "schema": _SCHEMA,
            "project": project,
            "case_digest": case_digest,
            "candidate_sha256": candidate_sha256,
            "operators": sorted(set(operators)),
            "public_failure_symptom": public_failure_symptom,
            "outcome": outcome,
            "freeze_digest": freeze_digest,
            "independent_evaluator_digest": independent_evaluator_digest,
            "role": "released_training",
            "is_independent_repair_proof": False,
            "code_or_human_patch_retained": False,
        }
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT event_digest FROM training_attempts ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            prior = previous[0] if previous else ""
            event = {**body, "previous_digest": prior}
            event_digest = digest_of(event)
            db.execute(
                """INSERT INTO training_attempts(previous_digest,event_digest,payload_json)
                VALUES(?,?,?)""",
                (prior, event_digest, json.dumps(event, sort_keys=True, separators=(",", ":"))),
            )
        return {**event, "event_digest": event_digest}

    def events(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            records = db.execute(
                "SELECT previous_digest,event_digest,payload_json FROM training_attempts ORDER BY sequence"
            ).fetchall()
        previous = ""
        result = []
        for parent, checksum, data in records:
            event = json.loads(data)
            if (parent != previous or event.get("previous_digest") != parent
                    or digest_of(event) != checksum):
                raise ValueError("tampered operator training history")
            previous = checksum
            result.append({**event, "event_digest": checksum})
        return result

    def evidence_summary(self) -> dict[str, Any]:
        """Summarize evidence by distinct cases, not by mutation spam.

        No self-promotion: future matched-budget validation must independently
        justify using the suggested values to alter candidate ordering.
        """
        collapsed: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for event in self.events():
            for operator in event["operators"]:
                collapsed[(operator, event["project"], event["case_digest"])].append(
                    event["outcome"]
                )
        summary = defaultdict(lambda: {"training_cases": 0, "training_projects": set(),
                                       "cases_with_full_suite_pass": 0,
                                       "cases_compile_failed_only": 0})
        for (operator, project, case_digest), outcomes in collapsed.items():
            record = summary[operator]
            record["training_cases"] += 1
            record["training_projects"].add(project)
            record["cases_with_full_suite_pass"] += int("full_suite_passed" in outcomes)
            record["cases_compile_failed_only"] += int(
                set(outcomes) == {"compile_failed"}
            )
        values = {}
        for operator, v in sorted(summary.items()):
            cases = v["training_cases"]
            projects = len(v["training_projects"])
            successes = v["cases_with_full_suite_pass"]
            values[operator] = {
                "distinct_training_cases": cases,
                "distinct_training_projects": projects,
                "cases_with_reported_full_suite_pass": successes,
                "cases_all_attempts_failed_compilation": v["cases_compile_failed_only"],
                "eligible_for_future_ranking_study": (
                    cases >= 5 and projects >= 3 and successes >= 2
                ),
                "ranking_automatically_changed": False,
            }
        events = self.events()
        body = {
            "schema": "genesis-operator-training-evidence-summary-v1",
            "event_count": len(events),
            "operator_evidence": values,
            "last_event_digest": events[-1]["event_digest"] if events else "",
            "independently_verified_repair_successes": 0,
            "user_or_operator_promotion_required": True,
        }
        return {**body, "summary_digest": digest_of(body)}
