"""Structured experimental memory for V51 development.

This module is deliberately evaluator-owned. It stores only observations already
revealed to the host and never gains authority over the evaluator, hidden targets
or acceptance rules. SQLite is the executable reference backend used by tests;
a PostgreSQL-compatible schema is shipped separately for deployment.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _signature(value: Iterable[float]) -> tuple[float, ...]:
    result = tuple(float(x) for x in value)
    if not result or any(not math.isfinite(x) for x in result):
        raise ValueError("Context signature must contain finite values")
    return result


@dataclass(frozen=True)
class MemoryHit:
    strategy_id: int
    semantic_sha256: str
    source_sha256: str
    genome: dict
    score: float
    similarity: float
    utility: float
    novelty: float
    confidence: float
    reuse_count: int
    success_count: int
    failure_count: int


class ExperimentalMemory:
    """Persistent, deduplicated and self-scoring experimental memory."""

    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self):
        self.db.close()

    def _migrate(self):
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategies(
                strategy_id INTEGER PRIMARY KEY,
                semantic_sha256 TEXT NOT NULL UNIQUE,
                source_sha256 TEXT NOT NULL,
                genome_json TEXT NOT NULL,
                behavior_sha256 TEXT NOT NULL UNIQUE,
                created_position INTEGER NOT NULL,
                last_seen_position INTEGER NOT NULL,
                utility REAL NOT NULL DEFAULT 0.0,
                novelty REAL NOT NULL DEFAULT 1.0,
                confidence REAL NOT NULL DEFAULT 0.5,
                reuse_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_success_position INTEGER
            );
            CREATE TABLE IF NOT EXISTS experiences(
                experience_id INTEGER PRIMARY KEY,
                task_sha256 TEXT NOT NULL,
                strategy_id INTEGER NOT NULL REFERENCES strategies(strategy_id),
                position INTEGER NOT NULL,
                context_json TEXT NOT NULL,
                context_signature_json TEXT NOT NULL,
                quality_milli INTEGER NOT NULL,
                solved INTEGER NOT NULL,
                evaluation_cost INTEGER NOT NULL,
                UNIQUE(task_sha256, strategy_id)
            );
            CREATE TABLE IF NOT EXISTS lineages(
                child_strategy_id INTEGER NOT NULL REFERENCES strategies(strategy_id),
                parent_source_sha256 TEXT,
                first_position INTEGER NOT NULL,
                PRIMARY KEY(child_strategy_id, parent_source_sha256)
            );
            CREATE TABLE IF NOT EXISTS evaluations(
                experience_id INTEGER PRIMARY KEY REFERENCES experiences(experience_id),
                quality_milli INTEGER NOT NULL,
                solved INTEGER NOT NULL,
                evaluation_cost INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_usage(
                usage_id INTEGER PRIMARY KEY,
                task_sha256 TEXT NOT NULL,
                strategy_id INTEGER NOT NULL REFERENCES strategies(strategy_id),
                position INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                retrieval_score REAL NOT NULL,
                impact_quality_milli INTEGER NOT NULL,
                impact_evaluations INTEGER NOT NULL,
                helpful INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS experiences_position_idx ON experiences(position);
            CREATE INDEX IF NOT EXISTS usage_strategy_idx ON memory_usage(strategy_id);
            """
        )
        current = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if current is None:
            self.db.execute("INSERT INTO meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        elif int(current["value"]) != SCHEMA_VERSION:
            raise ValueError("Unsupported experimental memory schema")
        self.db.commit()

    @staticmethod
    def observed_signature(root_quality_milli: int) -> tuple[float]:
        if type(root_quality_milli) is not int or not 0 <= root_quality_milli <= 1000:
            raise ValueError("Observed root quality must be integer milli-quality")
        return (root_quality_milli / 1000.0,)

    def remember_program(self, *, task_sha256, position, context, signature, program, evaluation_cost=1):
        signature = _signature(signature)
        semantic = program["semantic_sha256"]
        source = program["source_sha256"]
        genome = program["genome"]
        behavior = semantic  # exact V32 genome semantics; collapses source aliases by behavior
        quality = int(program["quality_milli"])
        solved = int(quality == 1000)
        parent = program.get("parent_source_sha256")
        with self.db:
            self.db.execute(
                """INSERT INTO strategies(
                    semantic_sha256,source_sha256,genome_json,behavior_sha256,
                    created_position,last_seen_position,last_success_position
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(semantic_sha256) DO UPDATE SET
                    last_seen_position=excluded.last_seen_position,
                    source_sha256=excluded.source_sha256""",
                (semantic, source, _json(genome), behavior, position, position, position if solved else None),
            )
            sid = self.db.execute(
                "SELECT strategy_id FROM strategies WHERE semantic_sha256=?", (semantic,)
            ).fetchone()["strategy_id"]
            self.db.execute(
                """INSERT OR IGNORE INTO experiences(
                    task_sha256,strategy_id,position,context_json,context_signature_json,
                    quality_milli,solved,evaluation_cost
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (task_sha256, sid, position, _json(context), _json(signature), quality, solved, evaluation_cost),
            )
            exp = self.db.execute(
                "SELECT experience_id FROM experiences WHERE task_sha256=? AND strategy_id=?",
                (task_sha256, sid),
            ).fetchone()["experience_id"]
            self.db.execute(
                """INSERT OR REPLACE INTO evaluations(
                    experience_id,quality_milli,solved,evaluation_cost
                ) VALUES(?,?,?,?)""",
                (exp, quality, solved, evaluation_cost),
            )
            self.db.execute(
                "INSERT OR IGNORE INTO lineages(child_strategy_id,parent_source_sha256,first_position) VALUES(?,?,?)",
                (sid, parent, position),
            )
            if solved:
                self.db.execute(
                    """UPDATE strategies SET
                        success_count=success_count+1,
                        last_success_position=?,
                        confidence=MIN(1.0, confidence+0.03)
                    WHERE strategy_id=?""",
                    (position, sid),
                )
            else:
                self.db.execute(
                    """UPDATE strategies SET
                        failure_count=failure_count+1,
                        confidence=MAX(0.05, confidence-0.005)
                    WHERE strategy_id=?""",
                    (sid,),
                )
        return sid

    def remember_episode(self, row):
        signature = self.observed_signature(row["root_evaluation"]["quality_milli"])
        context = {"root_quality_milli": row["root_evaluation"]["quality_milli"]}
        for program in row["programs"]:
            self.remember_program(
                task_sha256=row["task_sha256"],
                position=row["position"],
                context=context,
                signature=signature,
                program=program,
            )

    @staticmethod
    def _similarity(left, right):
        left, right = _signature(left), _signature(right)
        if len(left) != len(right):
            return 0.0
        return 1.0 / (1.0 + sum(abs(a - b) for a, b in zip(left, right)))

    def retrieve(self, signature, *, position, top_k=2, min_similarity=0.0, min_utility=-1.0,
                 compatible_width=None):
        signature = _signature(signature)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k must be positive")
        if not 0.0 <= min_similarity <= 1.0 or not -1.0 <= min_utility <= 1.0:
            raise ValueError("Invalid retrieval threshold")

        # A strategy may have succeeded under several observed contexts. Preserve
        # that full support set: V32's finite baseline ranks by the *nearest of all
        # prior successful contexts*, not merely the most recent one.
        rows = self.db.execute(
            """SELECT s.*, e.context_signature_json
               FROM strategies s
               JOIN experiences e ON e.strategy_id=s.strategy_id
               WHERE e.solved=1
               ORDER BY s.strategy_id, e.position"""
        ).fetchall()
        grouped = {}
        for row in rows:
            similarity = self._similarity(signature, json.loads(row["context_signature_json"]))
            previous = grouped.get(row["strategy_id"])
            if previous is None or similarity > previous[1]:
                grouped[row["strategy_id"]] = (row, similarity)

        hits = []
        for row, similarity in grouped.values():
            genome = json.loads(row["genome_json"])
            if compatible_width is not None and genome.get("width") != compatible_width:
                continue
            if similarity < min_similarity or row["utility"] < min_utility:
                continue
            age = max(0, position - (row["last_success_position"] or row["last_seen_position"]))
            age_factor = 1.0 / (1.0 + 0.02 * age)
            attempts = row["success_count"] + row["failure_count"]
            empirical = row["success_count"] / attempts if attempts else 0.5
            # Score is reported and used after the primary compatibility ordering.
            # Similarity remains dominant to preserve the observed V32 baseline;
            # utility/confidence break ties and can filter harmful memories.
            score = (
                0.80 * similarity
                + 0.08 * ((max(-1.0, min(1.0, row["utility"])) + 1.0) / 2.0)
                + 0.04 * row["confidence"]
                + 0.04 * empirical
                + 0.02 * row["novelty"]
                + 0.02 * age_factor
            )
            hits.append(MemoryHit(
                strategy_id=row["strategy_id"],
                semantic_sha256=row["semantic_sha256"],
                source_sha256=row["source_sha256"],
                genome=genome,
                score=score,
                similarity=similarity,
                utility=row["utility"],
                novelty=row["novelty"],
                confidence=row["confidence"],
                reuse_count=row["reuse_count"],
                success_count=row["success_count"],
                failure_count=row["failure_count"],
            ))
        hits.sort(key=lambda x: (
            -x.similarity,
            -x.utility,
            -x.confidence,
            -x.success_count,
            x.semantic_sha256,
        ))
        return hits[:top_k]

    def record_usage(self, *, task_sha256, hit, position, rank, impact_quality_milli, impact_evaluations):
        helpful = int(impact_quality_milli > 0 or impact_evaluations > 0)
        reward = max(-1.0, min(1.0, impact_quality_milli / 1000.0 + impact_evaluations / 14.0))
        with self.db:
            self.db.execute(
                """INSERT INTO memory_usage(
                    task_sha256,strategy_id,position,rank,retrieval_score,
                    impact_quality_milli,impact_evaluations,helpful
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (task_sha256, hit.strategy_id, position, rank, hit.score,
                 impact_quality_milli, impact_evaluations, helpful),
            )
            self.db.execute(
                """UPDATE strategies SET
                    reuse_count=reuse_count+1,
                    utility=0.8*utility+0.2*?,
                    confidence=CASE WHEN ? THEN MIN(1.0,confidence+0.04)
                                    ELSE MAX(0.05,confidence-0.04) END,
                    novelty=MAX(0.05, novelty*0.995)
                WHERE strategy_id=?""",
                (reward, helpful, hit.strategy_id),
            )

    def contribution(self):
        row = self.db.execute(
            """SELECT COUNT(*) AS uses,
                      COALESCE(SUM(helpful),0) AS helpful,
                      COALESCE(AVG(impact_quality_milli),0.0) AS avg_quality,
                      COALESCE(AVG(impact_evaluations),0.0) AS avg_evaluations
               FROM memory_usage"""
        ).fetchone()
        return {
            "uses": row["uses"],
            "helpful_uses": row["helpful"],
            "helpful_rate": (row["helpful"] / row["uses"]) if row["uses"] else 0.0,
            "avg_quality_impact_milli": row["avg_quality"],
            "avg_evaluation_savings": row["avg_evaluations"],
        }

    def counts(self):
        return {
            table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("strategies", "experiences", "lineages", "evaluations", "memory_usage")
        }
