"""Learned scaffold-refinement operators for V54."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import programs


def _bits(mask, width):
    return [bit for bit in range(width) if mask & (1 << bit)]


def _signed_rotation_delta(before, after, width):
    raw = (after - before) % width
    if raw > width // 2:
        raw -= width
    return raw


def derive_refinements(ancestor, descendant):
    """Distil local search progress into transferable scaffold operators."""
    ancestor = programs.validate(ancestor)
    descendant = programs.validate(descendant)
    if ancestor["width"] != descendant["width"]:
        raise ValueError("Refinement requires a same-width lineage")
    width = ancestor["width"]
    rotation_delta = _signed_rotation_delta(
        ancestor["rotation"], descendant["rotation"], width
    )
    toggled = _bits(ancestor["mask"] ^ descendant["mask"], width)
    high = [width - 1 - bit for bit in toggled]
    rows = []
    for mode, bits in (
        ("low", toggled),
        ("high", high),
        ("scaled", toggled),
    ):
        row = {
            "mode": mode,
            "source_width": width,
            "rotation_delta": rotation_delta,
            "bits": bits,
        }
        if rotation_delta or bits:
            rows.append(row)
    unique = {}
    for row in rows:
        unique.setdefault(digest(row), row)
    return tuple(unique.values())


def _scaled_bit(bit, old_width, new_width):
    if old_width <= 1:
        return 0
    return max(
        0,
        min(
            new_width - 1,
            round(bit * (new_width - 1) / (old_width - 1)),
        ),
    )


def apply_refinement(operator, genome):
    genome = programs.validate(genome)
    width = genome["width"]
    source_width = operator["source_width"]
    mode = operator["mode"]
    bits = operator["bits"]
    if mode == "low":
        mapped = [bit for bit in bits if bit < width]
    elif mode == "high":
        mapped = [
            width - 1 - offset for offset in bits
            if offset < width
        ]
    elif mode == "scaled":
        mapped = [
            _scaled_bit(bit, source_width, width) for bit in bits
        ]
    else:
        raise ValueError("Unknown refinement mode")
    mask = genome["mask"]
    for bit in mapped:
        mask ^= 1 << bit
    rotation = (
        genome["rotation"] + operator["rotation_delta"]
    ) % width
    return programs.validate({
        "width": width,
        "rotation": rotation,
        "mask": mask,
    })


@dataclass(frozen=True)
class RefinementHit:
    refinement_id: int
    operator: dict
    score: float
    lineage_depth: int
    support: int
    uses: int
    helpful: int
    failures: int
    utility: float


class RefinementMemory:
    """Persistent operators learned only from scaffold-descended successes."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS refinements(
            refinement_id INTEGER PRIMARY KEY,
            operator_sha256 TEXT NOT NULL UNIQUE,
            operator_json TEXT NOT NULL,
            source_width INTEGER NOT NULL,
            root_quality_milli INTEGER NOT NULL,
            lineage_depth INTEGER NOT NULL,
            support INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            helpful INTEGER NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0,
            utility REAL NOT NULL DEFAULT 0.0,
            last_position INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provenance(
            provenance_id INTEGER PRIMARY KEY,
            refinement_id INTEGER NOT NULL REFERENCES refinements(refinement_id),
            task_sha256 TEXT NOT NULL,
            ancestor_source_sha256 TEXT NOT NULL,
            descendant_source_sha256 TEXT NOT NULL,
            parent_refinement_id INTEGER,
            lineage_depth INTEGER NOT NULL,
            position INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage(
            usage_id INTEGER PRIMARY KEY,
            refinement_id INTEGER NOT NULL REFERENCES refinements(refinement_id),
            task_sha256 TEXT NOT NULL,
            position INTEGER NOT NULL,
            quality_delta_milli INTEGER NOT NULL,
            evaluation_delta INTEGER NOT NULL,
            helpful INTEGER NOT NULL
        );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def remember_episode(self, row):
        inserted = 0
        root_quality = row["root_evaluation"]["quality_milli"]
        for program in row["programs"]:
            if program["quality_milli"] != 1000:
                continue
            if not program.get("descended_from_scaffold"):
                continue
            # Store a cumulative refinement relative to the ordinary
            # V53 base scaffold, not merely the last injected refined scaffold.
            # A generation-3 operator therefore contains generation-2 progress
            # plus the newly learned local improvement and can be applied
            # directly to a fresh base scaffold on a later task.
            ancestor = program.get("scaffold_base_genome")
            ancestor_source = program.get(
                "scaffold_base_source_sha256"
            )
            if ancestor is None or ancestor_source is None:
                continue
            generation = int(program.get("scaffold_generation") or 0)
            if generation <= 0:
                continue
            next_depth = generation + 1
            parent_refinement_id = program.get(
                "scaffold_ancestor_refinement_id"
            )
            for operator in derive_refinements(
                ancestor, program["genome"]
            ):
                sha = digest(operator)
                payload = json.dumps(
                    operator, sort_keys=True, separators=(",", ":")
                )
                with self.db:
                    self.db.execute(
                        """INSERT INTO refinements(
                             operator_sha256,operator_json,source_width,
                             root_quality_milli,lineage_depth,last_position
                           ) VALUES(?,?,?,?,?,?)
                           ON CONFLICT(operator_sha256) DO UPDATE SET
                             support=support+1,
                             lineage_depth=MAX(lineage_depth,excluded.lineage_depth),
                             last_position=MAX(last_position,excluded.last_position)""",
                        (
                            sha,
                            payload,
                            operator["source_width"],
                            root_quality,
                            next_depth,
                            row["position"],
                        ),
                    )
                    refinement_id = self.db.execute(
                        """SELECT refinement_id FROM refinements
                           WHERE operator_sha256=?""",
                        (sha,),
                    ).fetchone()["refinement_id"]
                    self.db.execute(
                        """INSERT INTO provenance(
                             refinement_id,task_sha256,
                             ancestor_source_sha256,
                             descendant_source_sha256,
                             parent_refinement_id,lineage_depth,position
                           ) VALUES(?,?,?,?,?,?,?)""",
                        (
                            refinement_id,
                            row["task_sha256"],
                            ancestor_source,
                            program["source_sha256"],
                            parent_refinement_id,
                            next_depth,
                            row["position"],
                        ),
                    )
                inserted += 1
        return inserted

    def retrieve(self, *, root_quality_milli, width, position,
                 top_k=1, min_utility=-0.25):
        rows = self.db.execute(
            """SELECT * FROM refinements
               WHERE utility >= ?
               ORDER BY refinement_id""",
            (min_utility,),
        ).fetchall()
        hits = []
        for row in rows:
            operator = json.loads(row["operator_json"])
            quality_distance = abs(
                root_quality_milli - row["root_quality_milli"]
            )
            width_distance = abs(width - row["source_width"])
            recency = 1.0 / (
                1.0 + max(0, position - row["last_position"])
            )
            score = (
                1.0 / (1.0 + quality_distance / 25.0)
                + 0.18 * min(5, row["support"])
                + 0.30 * row["utility"]
                + 0.12 * min(4, row["lineage_depth"])
                + 0.08 * recency
                + 0.05 / (1.0 + width_distance)
            )
            hits.append(RefinementHit(
                refinement_id=row["refinement_id"],
                operator=operator,
                score=score,
                lineage_depth=row["lineage_depth"],
                support=row["support"],
                uses=row["uses"],
                helpful=row["helpful"],
                failures=row["failures"],
                utility=row["utility"],
            ))
        hits.sort(key=lambda hit: (
            -hit.score,
            -hit.lineage_depth,
            -hit.support,
            hit.refinement_id,
        ))
        return hits[:top_k]

    def record_usage(self, *, task_sha256, hit, position,
                     quality_delta_milli, evaluation_delta, helpful):
        helpful = int(bool(helpful))
        reward = max(-1.0, min(
            1.0,
            quality_delta_milli / 1000.0
            + max(-14, min(14, evaluation_delta)) / 28.0,
        ))
        if not helpful and reward > 0:
            reward = 0.0
        with self.db:
            self.db.execute(
                """INSERT INTO usage(
                     refinement_id,task_sha256,position,
                     quality_delta_milli,evaluation_delta,helpful
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    hit.refinement_id,
                    task_sha256,
                    position,
                    quality_delta_milli,
                    evaluation_delta,
                    helpful,
                ),
            )
            self.db.execute(
                """UPDATE refinements SET
                     uses=uses+1,
                     helpful=helpful+?,
                     failures=failures+?,
                     utility=0.8*utility+0.2*?,
                     last_position=MAX(last_position,?)
                   WHERE refinement_id=?""",
                (
                    helpful,
                    1-helpful,
                    reward,
                    position,
                    hit.refinement_id,
                ),
            )

    def counts(self):
        return {
            "refinements": self.db.execute(
                "SELECT COUNT(*) FROM refinements"
            ).fetchone()[0],
            "provenance": self.db.execute(
                "SELECT COUNT(*) FROM provenance"
            ).fetchone()[0],
            "usage": self.db.execute(
                "SELECT COUNT(*) FROM usage"
            ).fetchone()[0],
            "max_lineage_depth": self.db.execute(
                "SELECT COALESCE(MAX(lineage_depth),0) FROM refinements"
            ).fetchone()[0],
        }

    def lineage_depths(self):
        return {
            int(row["lineage_depth"]): int(row["count"])
            for row in self.db.execute(
                """SELECT lineage_depth,COUNT(*) AS count
                   FROM refinements
                   GROUP BY lineage_depth
                   ORDER BY lineage_depth"""
            )
        }
