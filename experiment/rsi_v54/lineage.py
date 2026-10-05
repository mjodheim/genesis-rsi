"""Recursive scaffold-descendant provenance for V54."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v52.abstractions import derive_recipes, instantiate

LINEAGE_MODES = ("low", "high", "scaled")


@dataclass(frozen=True)
class LineageHit:
    recipe_sha256: str
    recipe: dict
    genome: dict
    recursive_successes: int
    max_depth: int
    last_position: int
    score: float


class LineageMemory:
    """Stores full affine descendants that causally arose from prior scaffolds."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS descendant_recipes(
            recipe_sha256 TEXT PRIMARY KEY,
            recipe_json TEXT NOT NULL,
            recursive_successes INTEGER NOT NULL DEFAULT 0,
            max_depth INTEGER NOT NULL DEFAULT 0,
            last_position INTEGER NOT NULL DEFAULT -1
        );
        CREATE TABLE IF NOT EXISTS lineage_events(
            event_id INTEGER PRIMARY KEY,
            task_sha256 TEXT NOT NULL,
            semantic_sha256 TEXT NOT NULL,
            recipe_sha256 TEXT NOT NULL,
            parent_scaffold_key TEXT,
            recursive_depth INTEGER NOT NULL,
            search_depth INTEGER NOT NULL,
            position INTEGER NOT NULL
        );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def retrieve(self, *, width, position, top_k=1):
        rows = self.db.execute(
            """SELECT * FROM descendant_recipes
               ORDER BY recursive_successes DESC, max_depth DESC,
                        last_position DESC, recipe_sha256 ASC"""
        ).fetchall()
        hits = []
        seen = set()
        for row in rows:
            recipe = json.loads(row["recipe_json"])
            genome = instantiate(recipe, width)
            semantic = digest(genome)
            if semantic in seen:
                continue
            seen.add(semantic)
            age = max(0, position - row["last_position"])
            score = (
                0.40 * min(6, row["recursive_successes"])
                + 0.30 * min(4, row["max_depth"])
                + 0.15 / (1.0 + age)
            )
            hits.append(LineageHit(
                recipe_sha256=row["recipe_sha256"],
                recipe=recipe,
                genome=genome,
                recursive_successes=row["recursive_successes"],
                max_depth=row["max_depth"],
                last_position=row["last_position"],
                score=score,
            ))
        hits.sort(key=lambda hit: (
            -hit.score,
            -hit.recursive_successes,
            -hit.max_depth,
            -hit.last_position,
            hit.recipe_sha256,
        ))
        return hits[:top_k]

    def remember_episode(self, row):
        parent = {
            program["source_sha256"]: program["search_parent_source_sha256"]
            for program in row["programs"]
        }
        scaffold_meta = row["routing"]["scaffold_lineage"]

        def scaffold_ancestor(source):
            search_depth = 0
            seen = set()
            current = source
            while current and current not in seen:
                seen.add(current)
                meta = scaffold_meta.get(current)
                if meta is not None:
                    return meta, search_depth
                current = parent.get(current)
                search_depth += 1
            return None, None

        events = 0
        for program in row["programs"]:
            if program["quality_milli"] != 1000:
                continue
            meta, search_depth = scaffold_ancestor(program["source_sha256"])
            if meta is None:
                continue

            genome = program["genome"]
            # A recursive descendant must actually extend the scaffold into an
            # affine solution. Pure rotations are already handled by V53.
            if not genome["rotation"] or not genome["mask"]:
                continue

            recursive_depth = int(meta.get("max_depth", 0)) + 1
            for recipe in derive_recipes(genome):
                if recipe["mode"] not in LINEAGE_MODES:
                    continue
                sha = digest(recipe)
                payload = json.dumps(recipe, sort_keys=True, separators=(",", ":"))
                with self.db:
                    self.db.execute(
                        """INSERT INTO descendant_recipes(
                             recipe_sha256,recipe_json,recursive_successes,max_depth,last_position
                           ) VALUES(?,?,1,?,?)
                           ON CONFLICT(recipe_sha256) DO UPDATE SET
                             recursive_successes=recursive_successes+1,
                             max_depth=MAX(max_depth,excluded.max_depth),
                             last_position=MAX(last_position,excluded.last_position)""",
                        (sha, payload, recursive_depth, row["position"]),
                    )
                    self.db.execute(
                        """INSERT INTO lineage_events(
                             task_sha256,semantic_sha256,recipe_sha256,
                             parent_scaffold_key,recursive_depth,search_depth,position
                           ) VALUES(?,?,?,?,?,?,?)""",
                        (
                            row["task_sha256"],
                            program["semantic_sha256"],
                            sha,
                            meta.get("provenance_key"),
                            recursive_depth,
                            search_depth,
                            row["position"],
                        ),
                    )
                events += 1
        return events

    def counts(self):
        return {
            "recipes": self.db.execute(
                "SELECT COUNT(*) FROM descendant_recipes"
            ).fetchone()[0],
            "events": self.db.execute(
                "SELECT COUNT(*) FROM lineage_events"
            ).fetchone()[0],
            "max_depth": self.db.execute(
                "SELECT COALESCE(MAX(max_depth),0) FROM descendant_recipes"
            ).fetchone()[0],
        }
