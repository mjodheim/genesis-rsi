"""Trusted, opt-in domain diagnostics atop language understanding.

An insight is a *review suggestion*, not evidence of vulnerability, verified
performance gain, or benchmark repair success. No repository code is executed.
Only deliberately registered, trusted modules run inside the Genesis process.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Any, Mapping, Protocol

from genesis.languages.experience import ExperienceLedger
from genesis.languages.understanding import ModuleRegistry
from genesis.trust_root import digest_of

SCHEMA = "genesis-domain-insights-v1"
ALLOWED_DOMAINS = {"security", "performance"}
ALLOWED_CONFIDENCE = {"low", "medium"}
ALLOWED_LEVELS = {"review", "informational"}


class InsightModule(Protocol):
    module_id: str
    domain: str
    language: str

    def supports(self, report: Mapping[str, Any]) -> bool: ...
    def scan(self, source: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]: ...


class InsightRegistry:
    """Explicit domain module registry; reporting and ledger remain detached."""

    def __init__(self) -> None:
        self._modules: dict[str, InsightModule] = {}

    def register(self, module: InsightModule) -> None:
        if module.domain not in ALLOWED_DOMAINS:
            raise ValueError("unsupported diagnostic domain")
        if not module.module_id or not module.language:
            raise ValueError("module requires identity and language")
        if not callable(getattr(module, "scan", None)) or not callable(getattr(module, "supports", None)):
            raise ValueError("module requires supports() and scan()")
        if module.module_id in self._modules:
            raise ValueError("module already registered")
        self._modules[module.module_id] = module

    def remove(self, module_id: str) -> bool:
        return self._modules.pop(module_id, None) is not None

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._modules))

    def inspect(
        self,
        source: str | Path,
        *,
        languages: ModuleRegistry | None = None,
        ledger: ExperienceLedger | None = None,
        understanding: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = Path(source).resolve(strict=True)
        if understanding is None:
            if languages is None:
                raise ValueError("language registry or a precomputed report is required")
            understanding = languages.analyze(path)
        # The analyzer records must be authentic and match the *current* source.
        unsigned = {k: v for k, v in understanding.items() if k != "analysis_digest"}
        if understanding.get("analysis_digest") != digest_of(unsigned):
            raise ValueError("invalid understanding digest")
        if understanding["module_id"] == "genesis-substrate-v1":
            expected_source = digest_of({"source": path.read_text(encoding="utf-8")})
        elif understanding["module_id"] == "jdk-java-compiler-v2":
            expected_source = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            expected_source = digest_of({"source_bytes_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if understanding["source_digest"] != expected_source:
            raise ValueError("understanding analysis is stale for this source")
        findings: list[dict[str, Any]] = []
        checked: list[str] = []
        skipped: list[str] = []
        coverage = {"security": "not_supported", "performance": "not_supported"}
        for module_id, module in sorted(self._modules.items()):
            if module.language != understanding["language"]:
                continue
            if not module.supports(understanding):
                skipped.append(module_id)
                if coverage[module.domain] != "checked":
                    coverage[module.domain] = "insufficient_fidelity"
                continue
            checked.append(module_id)
            coverage[module.domain] = "checked"
            records = module.scan(path, understanding)
            for record in records:
                if record.get("confidence") not in ALLOWED_CONFIDENCE:
                    raise ValueError("unsupported confidence")
                if record.get("level") not in ALLOWED_LEVELS:
                    raise ValueError("unsupported warning level")
                rule = record.get("rule_id")
                if not isinstance(rule, str) or not rule or len(rule) > 80:
                    raise ValueError("missing or invalid rule id")
                # Domain modules are *sensors*: no snippet or fix suggestion is
                # required; only auditable source locations and review reason.
                finding = {
                    "domain": module.domain,
                    "module_id": module_id,
                    "rule_id": rule,
                    "confidence": record["confidence"],
                    "level": record["level"],
                    "line": int(record["line"]),
                    "reason": str(record.get("reason") or ""),
                    "verified_problem": False,
                    "requires_human_or_independent_validation": True,
                }
                if finding["line"] < 1 or not finding["reason"]:
                    raise ValueError("invalid finding")
                findings.append(finding)
                if ledger is not None:
                    ledger.record(understanding, operator=f"{module.domain}:{rule}")
        payload = {
            "schema": SCHEMA,
            "source_sha_or_digest": understanding["source_digest"],
            "analysis_digest": understanding["analysis_digest"],
            "language": understanding["language"],
            "fidelity": understanding["fidelity"],
            "checked_modules": checked,
            "coverage_by_domain": coverage,
            "skipped_modules_due_to_insufficient_fidelity": skipped,
            "findings": findings,
            "findings_are_review_hints_not_proven_bugs": True,
            "security_cleared": False,
            "performance_improvement_proven": False,
            "external_model_calls": 0,
        }
        return {**payload, "insight_digest": digest_of(payload)}
