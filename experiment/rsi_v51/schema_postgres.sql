-- PostgreSQL deployment schema for the V51 experimental memory.
-- The Python test/reference backend uses SQLite with the same logical tables.
CREATE TABLE IF NOT EXISTS strategies (
  strategy_id BIGSERIAL PRIMARY KEY,
  semantic_sha256 CHAR(64) NOT NULL UNIQUE,
  source_sha256 CHAR(64) NOT NULL,
  genome_json JSONB NOT NULL,
  behavior_sha256 CHAR(64) NOT NULL UNIQUE,
  created_position BIGINT NOT NULL,
  last_seen_position BIGINT NOT NULL,
  utility DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  novelty DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  reuse_count BIGINT NOT NULL DEFAULT 0,
  success_count BIGINT NOT NULL DEFAULT 0,
  failure_count BIGINT NOT NULL DEFAULT 0,
  last_success_position BIGINT
);
CREATE TABLE IF NOT EXISTS experiences (
  experience_id BIGSERIAL PRIMARY KEY,
  task_sha256 CHAR(64) NOT NULL,
  strategy_id BIGINT NOT NULL REFERENCES strategies(strategy_id),
  position BIGINT NOT NULL,
  context_json JSONB NOT NULL,
  context_signature_json JSONB NOT NULL,
  quality_milli INTEGER NOT NULL CHECK (quality_milli BETWEEN 0 AND 1000),
  solved BOOLEAN NOT NULL,
  evaluation_cost INTEGER NOT NULL CHECK (evaluation_cost >= 0),
  UNIQUE(task_sha256, strategy_id)
);
CREATE TABLE IF NOT EXISTS lineages (
  child_strategy_id BIGINT NOT NULL REFERENCES strategies(strategy_id),
  parent_source_sha256 CHAR(64),
  first_position BIGINT NOT NULL,
  PRIMARY KEY(child_strategy_id, parent_source_sha256)
);
CREATE TABLE IF NOT EXISTS evaluations (
  experience_id BIGINT PRIMARY KEY REFERENCES experiences(experience_id),
  quality_milli INTEGER NOT NULL CHECK (quality_milli BETWEEN 0 AND 1000),
  solved BOOLEAN NOT NULL,
  evaluation_cost INTEGER NOT NULL CHECK (evaluation_cost >= 0)
);
CREATE TABLE IF NOT EXISTS memory_usage (
  usage_id BIGSERIAL PRIMARY KEY,
  task_sha256 CHAR(64) NOT NULL,
  strategy_id BIGINT NOT NULL REFERENCES strategies(strategy_id),
  position BIGINT NOT NULL,
  rank INTEGER NOT NULL,
  retrieval_score DOUBLE PRECISION NOT NULL,
  impact_quality_milli INTEGER NOT NULL,
  impact_evaluations INTEGER NOT NULL,
  helpful BOOLEAN NOT NULL
);
CREATE INDEX IF NOT EXISTS experiences_position_idx ON experiences(position);
CREATE INDEX IF NOT EXISTS memory_usage_strategy_idx ON memory_usage(strategy_id);
