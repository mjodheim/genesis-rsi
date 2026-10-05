"""Recursive scaffold provenance and lineage credit for V54."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v52.abstractions import derive_recipes


@dataclass(frozen=True)
class LineageCredit:
    recipe_sha256: str
    recursive_successes: int
    max_depth: int
    last_position: int

    @property
    def score(self):
        return min(6, self.recursive_successes) * 0.30 + min(4, self.max_depth) * 0.20


class LineageMemory:
    """Tracks recipes produced by successful descendants of prior scaffolds."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS lineage_recipes(
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
            parent_scaffold_recipe_id INTEGER,
            recursive_depth INTEGER NOT NULL,
            position INTEGER NOT NULL
        );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def credit_for(self, recipe):
        sha = digest(recipe)
        row = self.db.execute(
            "SELECT * FROM lineage_recipes WHERE recipe_sha256=?", (sha,)
        ).fetchone()
        if row is None:
            return LineageCredit(sha, 0, 0, -1)
        return LineageCredit(
            recipe_sha256=sha,
            recursive_successes=row["recursive_successes"],
            max_depth=row["max_depth"],
            last_position=row["last_position"],
        )

    def remember_episode(self, row):
        programs = {program["source_sha256"]: program for program in row["programs"]}
        parent = {
            program["source_sha256"]: program["search_parent_source_sha256"]
            for program in row["programs"]
        }
        scaffold_map = dict(zip(
            row["routing"]["scaffold_sources"],
            row["routing"]["scaffold_recipe_ids"],
        ))

        def scaffold_ancestor(source):
            depth = 0
            seen = set()
            current = source
            while current and current not in seen:
                seen.add(current)
                if current in scaffold_map:
                    return scaffold_map[current], depth
                current = parent.get(current)
                depth += 1
            return None, None

        events = 0
        for program in row["programs"]:
            if program["quality_milli"] != 1000:
                continue
            scaffold_recipe_id, depth = scaffold_ancestor(program["source_sha256"])
            if scaffold_recipe_id is None:
                continue
            recursive_depth = max(1, depth)
            for recipe in derive_recipes(program["genome"]):
                # V54 recursion is specifically about future scaffold material.
                if recipe["mode"] != "rotation":
                    continue
                sha = digest(recipe)
                payload = json.dumps(recipe, sort_keys=True, separators=(",", ":"))
                with self.db:
                    self.db.execute(
                        """INSERT INTO lineage_recipes(
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
                             parent_scaffold_recipe_id,recursive_depth,position
                           ) VALUES(?,?,?,?,?,?)""",
                        (
                            row["task_sha256"],
                            program["semantic_sha256"],
                            sha,
                            scaffold_recipe_id,
                            recursive_depth,
                            row["position"],
                        ),
                    )
                events += 1
        return events

    def counts(self):
        return {
            "recipes": self.db.execute(
                "SELECT COUNT(*) FROM lineage_recipes"
            ).fetchone()[0],
            "events": self.db.execute(
                "SELECT COUNT(*) FROM lineage_events"
            ).fetchone()[0],
            "max_depth": self.db.execute(
                "SELECT COALESCE(MAX(max_depth),0) FROM lineage_recipes"
            ).fetchone()[0],
        }
