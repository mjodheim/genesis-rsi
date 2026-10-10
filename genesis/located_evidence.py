"""Repair evidence whose suspect locations are given, not computed here.

``localized_evidence`` runs one module on a checkout. A program over several archived modules has
its locations computed elsewhere, from answers stored once. This gives the repair agent the same
evidence with the production excerpts taken around such locations, so that two arms differ only
by where they are told to look.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from genesis import localizer_lineage as lineage
from genesis.repair_bench import _excerpts
from genesis.trust_root import digest_of


def located(evidence: Mapping, root: Path, locations: Sequence[Sequence], origin: str, *,
            source_budget: int = 48_000) -> dict:
    """``evidence`` read around ``locations``; the collected evidence is kept when none is usable."""
    root = Path(root)
    prefix = evidence["source_directory"].strip("/") + "/"
    usable = [item for item in lineage.clean_locations(list(locations))
              if item[0].startswith(prefix) and item[0].endswith(".java") and (root / item[0]).is_file()]
    body = {name: value for name, value in evidence.items() if name != "evidence_digest"}
    if usable:
        body.update(suspect_locations=usable, suspects_from_stack_trace=True,
                    production_source=_excerpts(root, [tuple(item) for item in usable], lineage.WINDOW, source_budget))
    body["localization"] = {"origin": origin, "locations": len(usable), "fallback": not usable}
    return {**body, "evidence_digest": digest_of(body)}
