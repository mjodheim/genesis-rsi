[Reading 266 lines from start (total: 266 lines, 0 remaining)]

"""Cross-width abstraction memory for V52 development."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import programs


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _bits(mask, width):
    return [bit for bit in range(width) if mask & (1 << bit)]


def _map_scaled(value, old_width, new_width, *, rotation=False):
    if value == 0:
        return 0
    denominator = old_width if rotation else max(1, old_width - 1)
    numerator = new_width if rotation else max(1, new_width - 1)
    mapped = round(value * numerator / denominator)
    if rotation:
        return mapped % new_width
    return max(0, min(new_width - 1, mapped))


def derive_recipes(genome):
    """Distil executable cross-width recipes from one successful genome."""
    genome = programs.validate(genome)
    width, rotation, mask = genome["width"], genome["rotation"], genome["mask"]
    bits = _bits(mask, width)
    high = [width - 1 - bit for bit in bits]
    recipes = [
        {"mode": "low", "source_width": width, "rotation": rotation, "bits": bits},
        {"mode": "high", "source_width": width, "rotation": rotation, "bits": high},
        {"mode": "scaled", "source_width": width, "rotation": rotation, "bits": bits},
    ]
    if rotation:
        recipes.append({"mode": "rotation", "source_width": width, "rotation": rotation, "bits": []})
    if bits:
        recipes.append({"mode": "mask_low", "source_width": width, "rotation": 0, "bits": bits})
        recipes.append({"mode": "mask_high", "source_width": width, "rotation": 0, "bits": high})
        recipes.append({"mode": "mask_scaled", "source_width": width, "rotation": 0, "bits": bits})
    unique = {}
    for recipe in recipes:
        unique.setdefault(digest(recipe), recipe)
    return tuple(unique.values())


def instantiate(recipe, width):
    if type(width) is not int or not 2 <= width <= 64:
        raise ValueError("Invalid target width")
    source_width = recipe["source_width"]
    mode = recipe["mode"]
    rotation = recipe["rotation"]
    bits = recipe["bits"]
    if mode in ("low", "mask_low", "rotation"):
        mapped_rotation = rotation if rotation < width else rotation % width
        mapped_bits = [bit for bit in bits if bit < width]
    elif mode in ("high", "mask_high"):
        mapped_rotation = rotation if rotation < width else rotation % width
        mapped_bits = [width - 1 - offset for offset in bits if offset < width]
    elif mode in ("scaled", "mask_scaled"):
        mapped_rotation = _map_scaled(rotation, source_width, width, rotation=True)
        mapped_bits = [_map_scaled(bit, source_width, width) for bit in bits]
    else:
        raise ValueError("Unknown abstraction mode")
    mask = 0
    for bit in mapped_bits:
        mask |= 1 << bit
    return programs.validate({"width": width, "rotation": mapped_rotation, "mask": mask})


@dataclass(frozen=True)
class AbstractHit:
    recipe_id: int
    recipe: dict
    score: float
    support: int
    success_count: int
    failure_count: int
    utility: float


class AbstractionMemory:
    """Persistent recipe memory distilled only from already successful programs."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS recipes(
            recipe_id INTEGER PRIMARY KEY,
            recipe_sha256 TEXT NOT NULL UNIQUE,
            recipe_json TEXT NOT NULL,
            support INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            utility REAL NOT NULL DEFAULT 0.0,
            last_success_position INTEGER NOT NULL DEFAULT -1
        );
        CREATE TABLE IF NOT EXISTS contexts(
            recipe_id INTEGER NOT NULL REFERENCES recipes(recipe_id),
            root_quality_milli INTEGER NOT NULL,
            source_width INTEGER NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY(recipe_id, root_quality_milli, source_width, position)
        );
        CREATE TABLE IF NOT EXISTS usage(
            usage_id INTEGER PRIMARY KEY,
            task_sha256 TEXT NOT NULL,
            recipe_id INTEGER NOT NULL REFERENCES recipes(recipe_id),
            position INTEGER NOT NULL,
            quality_delta_milli INTEGER NOT NULL,
            evaluation_delta INTEGER NOT NULL,
            helpful INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS width_policy(
            width INTEGER PRIMARY KEY,
            uses INTEGER NOT NULL DEFAULT 0,
            helpful INTEGER NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            disabled INTEGER NOT NULL DEFAULT 0
        );
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def remember_episode(self, row):
        root_quality = row["root_evaluation"]["quality_milli"]
        for program in row["programs"]:
            if program["quality_milli"] != 1000:
                continue
            for recipe in derive_recipes(program["genome"]):
                sha = digest(recipe)
                with self.db:
                    self.db.execute(
                        """INSERT INTO recipes(recipe_sha256,recipe_json,support,success_count,last_success_position)
                           VALUES(?,?,1,1,?)
                           ON CONFLICT(recipe_sha256) DO UPDATE SET
                             support=support+1,
                             success_count=success_count+1,
                             last_success_position=MAX(last_success_position,excluded.last_success_position)""",
                        (sha, _json(recipe), row["position"]),
                    )
                    rid = self.db.execute(
                        "SELECT recipe_id FROM recipes WHERE recipe_sha256=?", (sha,)
                    ).fetchone()["recipe_id"]
                    self.db.execute(
                        """INSERT OR IGNORE INTO contexts(
                             recipe_id,root_quality_milli,source_width,position
                           ) VALUES(?,?,?,?)""",
                        (rid, root_quality, program["genome"]["width"], row["position"]),
                    )

    def retrieve(self, *, root_quality_milli, width, position, top_k=4, min_utility=-0.10, allowed_modes=None):
        rows = self.db.execute(
            """SELECT r.*, c.root_quality_milli, c.source_width
               FROM recipes r JOIN contexts c ON c.recipe_id=r.recipe_id"""
        ).fetchall()
        grouped = {}
        for row in rows:
            distance = abs(root_quality_milli - row["root_quality_milli"])
            width_distance = abs(width - row["source_width"])
            old = grouped.get(row["recipe_id"])
            key = (distance, width_distance)
            if old is None or key < old[0]:
                grouped[row["recipe_id"]] = (key, row)
        hits = []
        seen_genomes = set()
        for (distance, width_distance), row in grouped.values():
            if row["utility"] < min_utility:
                continue
            recipe = json.loads(row["recipe_json"])
            if allowed_modes is not None and recipe["mode"] not in allowed_modes:
                continue
            genome = instantiate(recipe, width)
            semantic = digest(genome)
            if semantic in seen_genomes:
                continue
            seen_genomes.add(semantic)
            score = (
                1.0 / (1.0 + distance / 25.0)
                + 0.20 * min(5, row["support"])
                + 0.10 * min(5, row["success_count"])
                + 0.25 * row["utility"]
                + 0.05 / (1.0 + width_distance)
            )
            hits.append(AbstractHit(
                recipe_id=row["recipe_id"], recipe=recipe, score=score,
                support=row["support"], success_count=row["success_count"],
                failure_count=row["failure_count"], utility=row["utility"],
            ))
        hits.sort(key=lambda hit: (-hit.score, -hit.support, hit.recipe_id))
        return hits[:top_k]

    def record_usage(self, *, task_sha256, hit, position, quality_delta_milli, evaluation_delta):
        # Abstraction is retained for discovery only when it improves observed
        # quality over the exact-memory baseline. A no-gain recall is retired
        # aggressively so later tasks explore a different abstraction.
        helpful = int(quality_delta_milli > 0)
        reward = max(-1.0, min(1.0, quality_delta_milli / 1000.0)) if helpful else -1.0
        with self.db:
            self.db.execute(
                """INSERT INTO usage(task_sha256,recipe_id,position,quality_delta_milli,evaluation_delta,helpful)
                   VALUES(?,?,?,?,?,?)""",
                (task_sha256, hit.recipe_id, position, quality_delta_milli, evaluation_delta, helpful),
            )
            self.db.execute(
                """UPDATE recipes SET
                     utility=0.8*utility+0.2*?,
                     success_count=success_count+?,
                     failure_count=failure_count+?
                   WHERE recipe_id=?""",
                (reward, helpful, 1 - helpful, hit.recipe_id),
            )

    def width_enabled(self, width):
        row = self.db.execute(
            "SELECT disabled FROM width_policy WHERE width=?", (width,)
        ).fetchone()
        return row is None or not bool(row["disabled"])

    def record_width_outcome(self, *, width, helpful, failure_limit=2):
        if failure_limit < 1:
            raise ValueError("failure_limit must be positive")
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO width_policy(width) VALUES(?)", (width,)
            )
            row = self.db.execute(
                "SELECT consecutive_failures FROM width_policy WHERE width=?", (width,)
            ).fetchone()
            failures = 0 if helpful else row["consecutive_failures"] + 1
            self.db.execute(
                """UPDATE width_policy SET
                     uses=uses+1,
                     helpful=helpful+?,
                     consecutive_failures=?,
                     disabled=CASE WHEN ? >= ? THEN 1 ELSE disabled END
                   WHERE width=?""",
                (int(helpful), failures, failures, failure_limit, width),
            )

    def width_policy(self):
        return [
            dict(row) for row in self.db.execute(
                "SELECT * FROM width_policy ORDER BY width"
            ).fetchall()
        ]

    def counts(self):
        return {
            "recipes": self.db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0],
            "contexts": self.db.execute("SELECT COUNT(*) FROM contexts").fetchone()[0],
            "usage": self.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0],
            "width_policy": self.db.execute("SELECT COUNT(*) FROM width_policy").fetchone()[0],
        }

[executed on device: Mjodheim-Ubuntu-cx33 (915d6eb6-54f1-400c-8c12-a1e043b0a356)]