"""Persistent experience graph for OE1.

SQLite is supported for deterministic tests. PostgreSQL is the intended VPS backend
for concurrent long-lived OE research.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from experiment.rsi_v25.commitments import digest


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS oe_runs(
        run_id TEXT PRIMARY KEY,
        code_sha TEXT NOT NULL,
        scope TEXT NOT NULL,
        created_at TEXT NOT NULL,
        metadata_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oe_tasks(
        task_sha256 TEXT PRIMARY KEY,
        family TEXT,
        width INTEGER,
        window INTEGER,
        payload_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oe_improvers(
        improver_sha256 TEXT PRIMARY KEY,
        parent_sha256 TEXT,
        generation INTEGER NOT NULL,
        genome_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oe_candidates(
        candidate_sha256 TEXT PRIMARY KEY,
        genome_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oe_evaluations(
        evaluation_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        task_sha256 TEXT NOT NULL,
        improver_sha256 TEXT NOT NULL,
        candidate_sha256 TEXT NOT NULL,
        parent_candidate_sha256 TEXT,
        origin TEXT NOT NULL,
        quality_milli INTEGER NOT NULL,
        solved INTEGER NOT NULL,
        charged_cost INTEGER NOT NULL,
        position INTEGER NOT NULL,
        window INTEGER,
        descriptor_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS oe_archive(
        niche_key TEXT PRIMARY KEY,
        improver_sha256 TEXT NOT NULL,
        quality REAL NOT NULL,
        novelty REAL NOT NULL,
        learning_progress REAL NOT NULL,
        children INTEGER NOT NULL,
        descriptor_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ExperienceStore:
    def __init__(self, dsn):
        self.dsn = dsn
        self.kind = "sqlite" if dsn.startswith("sqlite:///") else "postgres"
        if self.kind == "sqlite":
            path = dsn.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path)
            self.db.row_factory = sqlite3.Row
        else:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL OE1 storage requires pip install -e '.[oe]'"
                ) from exc
            self.db = psycopg.connect(dsn, row_factory=dict_row)
        self.init_schema()

    def close(self):
        self.db.close()

    def _sql(self, sql):
        return sql if self.kind == "sqlite" else sql.replace("?", "%s")

    def execute(self, sql, params=()):
        cur = self.db.cursor()
        try:
            cur.execute(self._sql(sql), params)
            self.db.commit()
            return cur
        except Exception:
            self.db.rollback()
            cur.close()
            raise

    def fetchall(self, sql, params=()):
        cur = self.db.cursor()
        try:
            cur.execute(self._sql(sql), params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()

    def fetchone(self, sql, params=()):
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def init_schema(self):
        for statement in SCHEMA:
            cur = self.db.cursor()
            try:
                cur.execute(statement)
            finally:
                cur.close()
        self.db.commit()

    def create_run(self, *, code_sha, scope, metadata=None, run_id=None):
        run_id = run_id or str(uuid4())
        self.execute(
            """INSERT INTO oe_runs(run_id,code_sha,scope,created_at,metadata_json)
               VALUES(?,?,?,?,?)""",
            (
                run_id,
                code_sha,
                scope,
                datetime.now(timezone.utc).isoformat(),
                _json(metadata or {}),
            ),
        ).close()
        return run_id

    def upsert_task(self, task):
        task_sha = digest(task)
        self.execute(
            """INSERT INTO oe_tasks(task_sha256,family,width,window,payload_json)
               VALUES(?,?,?,?,?)
               ON CONFLICT(task_sha256) DO UPDATE SET
                 family=excluded.family,
                 width=excluded.width,
                 window=excluded.window,
                 payload_json=excluded.payload_json""",
            (
                task_sha,
                task.get("family"),
                task.get("width"),
                task.get("window"),
                _json(task),
            ),
        ).close()
        return task_sha

    def upsert_improver(self, genome, *, parent_sha256=None, generation=0):
        improver_sha = genome.sha256()
        self.execute(
            """INSERT INTO oe_improvers(
                 improver_sha256,parent_sha256,generation,genome_json,created_at
               ) VALUES(?,?,?,?,?)
               ON CONFLICT(improver_sha256) DO NOTHING""",
            (
                improver_sha,
                parent_sha256,
                generation,
                _json(genome.canonical()),
                datetime.now(timezone.utc).isoformat(),
            ),
        ).close()
        return improver_sha

    def upsert_candidate(self, candidate, *, candidate_sha256=None):
        candidate_sha = candidate_sha256 or digest(candidate)
        self.execute(
            """INSERT INTO oe_candidates(candidate_sha256,genome_json)
               VALUES(?,?)
               ON CONFLICT(candidate_sha256) DO NOTHING""",
            (candidate_sha, _json(candidate)),
        ).close()
        return candidate_sha

    def record_evaluation(
        self,
        *,
        run_id,
        task_sha256,
        improver_sha256,
        candidate,
        candidate_sha256=None,
        parent_candidate_sha256,
        origin,
        quality_milli,
        solved,
        charged_cost,
        position,
        window,
        descriptor=None,
    ):
        candidate_sha = self.upsert_candidate(
            candidate, candidate_sha256=candidate_sha256
        )
        evaluation_id = str(uuid4())
        self.execute(
            """INSERT INTO oe_evaluations(
                 evaluation_id,run_id,task_sha256,improver_sha256,
                 candidate_sha256,parent_candidate_sha256,origin,
                 quality_milli,solved,charged_cost,position,window,descriptor_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                evaluation_id,
                run_id,
                task_sha256,
                improver_sha256,
                candidate_sha,
                parent_candidate_sha256,
                origin,
                int(quality_milli),
                int(bool(solved)),
                int(charged_cost),
                int(position),
                window,
                _json(descriptor or {}),
            ),
        ).close()
        return evaluation_id

    def record_episode(self, *, run_id, improver_sha256, task, row):
        task_sha = self.upsert_task(task)
        for program in row["programs"]:
            parent = program.get("search_parent_source_sha256")
            descriptor = {
                "candidate_origin": program.get("candidate_origin", "search"),
                "task_family": task.get("family"),
                "width": task.get("width"),
                "window": task.get("window"),
                "root_quality_milli": row["root_evaluation"]["quality_milli"],
                "depth_hint": 0 if parent is None else 1,
            }
            self.record_evaluation(
                run_id=run_id,
                task_sha256=task_sha,
                improver_sha256=improver_sha256,
                candidate=program["genome"],
                candidate_sha256=program["source_sha256"],
                parent_candidate_sha256=parent,
                origin=program.get("candidate_origin", "search"),
                quality_milli=program["quality_milli"],
                solved=program["quality_milli"] == 1000,
                charged_cost=1,
                position=row["position"],
                window=task.get("window"),
                descriptor=descriptor,
            )
        return task_sha

    def task_graph(self, task_sha256):
        return self.fetchall(
            """SELECT e.*, c.genome_json
               FROM oe_evaluations e
               JOIN oe_candidates c ON c.candidate_sha256=e.candidate_sha256
               WHERE e.task_sha256=?
               ORDER BY e.position, e.evaluation_id""",
            (task_sha256,),
        )

    def all_task_ids(self):
        return [
            row["task_sha256"]
            for row in self.fetchall(
                "SELECT task_sha256 FROM oe_tasks ORDER BY task_sha256"
            )
        ]

    def save_elite(
        self,
        *,
        niche_key,
        improver_sha256,
        quality,
        novelty,
        learning_progress,
        children,
        descriptor,
    ):
        self.execute(
            """INSERT INTO oe_archive(
                 niche_key,improver_sha256,quality,novelty,learning_progress,
                 children,descriptor_json,updated_at
               ) VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(niche_key) DO UPDATE SET
                 improver_sha256=excluded.improver_sha256,
                 quality=excluded.quality,
                 novelty=excluded.novelty,
                 learning_progress=excluded.learning_progress,
                 children=excluded.children,
                 descriptor_json=excluded.descriptor_json,
                 updated_at=excluded.updated_at""",
            (
                niche_key,
                improver_sha256,
                float(quality),
                float(novelty),
                float(learning_progress),
                int(children),
                _json(descriptor),
                datetime.now(timezone.utc).isoformat(),
            ),
        ).close()

    def archive(self):
        return self.fetchall(
            """SELECT * FROM oe_archive
               ORDER BY quality DESC, novelty DESC, learning_progress DESC"""
        )
