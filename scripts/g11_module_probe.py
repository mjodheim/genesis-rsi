#!/usr/bin/env python3
"""Run non-executing G11 language + security/performance review modules.

Only files named explicitly are analyzed; no hidden benchmark data or human
fix is accessed. Reports are review hints and do not justify repair success.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.insights import (
    InsightRegistry, JavaSecurityModule, PythonSecurityModule,
    JavaPerformanceModule, PythonPerformanceModule,
)
from genesis.languages.experience import ExperienceLedger
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry
from genesis.trust_root import digest_of


def _java_bin() -> Path | None:
    home = os.environ.get("JAVA_HOME", "").strip()
    locations = [
        Path(home) / "bin" if home else None,
        Path("/home/anthony/tools/jdk11/bin"),
    ]
    for location in locations:
        if location and (location / "java").is_file() and (location / "javac").is_file():
            return location
    java = shutil.which("java")
    javac = shutil.which("javac")
    if java and javac:
        return Path(java).parent
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="explicit source paths; max 24 files")
    parser.add_argument("--experience-db", type=Path,
                        help="opt-in training-only SQLite observations; do not use evaluation cases")
    parser.add_argument("--language-compiler", action="store_true",
                        help="enable JDK analyzer for Java (otherwise lexical fallback)")
    parser.add_argument("--security", action="store_true", help="static security review hints")
    parser.add_argument("--performance", action="store_true", help="static performance review hints")
    args = parser.parse_args(argv)
    if len(args.files) > 24:
        parser.error("maximum 24 explicit files")
    if not args.security and not args.performance:
        parser.error("select --security, --performance, or both")
    languages = ModuleRegistry()
    if args.language_compiler:
        bindir = _java_bin()
        if bindir is None:
            parser.error("JDK with java and javac is required for --language-compiler")
        languages.register(JavaCompilerModule(java=bindir / "java", javac=bindir / "javac"))
    insights = InsightRegistry()
    if args.security:
        insights.register(PythonSecurityModule())
        insights.register(JavaSecurityModule())
    if args.performance:
        insights.register(PythonPerformanceModule())
        insights.register(JavaPerformanceModule())
    ledger = ExperienceLedger(args.experience_db) if args.experience_db else None
    reports = []
    for path in args.files:
        outcome = insights.inspect(path, languages=languages, ledger=ledger)
        reports.append({
            "filename": path.name,
            "language": outcome["language"],
            "fidelity": outcome["fidelity"],
            "coverage_by_domain": outcome["coverage_by_domain"],
            "findings": outcome["findings"],
            "insight_digest": outcome["insight_digest"],
        })
    body = {
        "schema": "genesis-g11-probe-bundle-v1",
        "file_count": len(reports),
        "review_hint_count": sum(len(record["findings"]) for record in reports),
        "reports": reports,
        "ledger_summary_digest": ledger.knowledge_summary()["summary_digest"] if ledger else None,
        "findings_are_unverified_review_hints": True,
        "no_repository_code_executed": True,
        "external_model_calls": 0,
    }
    print(json.dumps({**body, "report_digest": digest_of(body)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
