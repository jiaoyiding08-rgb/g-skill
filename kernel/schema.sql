PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS intents (
  intent_id TEXT PRIMARY KEY, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS completion_contracts (
  contract_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
  payload TEXT NOT NULL CHECK(json_valid(payload)), PRIMARY KEY(contract_id, version)
);
CREATE TABLE IF NOT EXISTS action_runs (
  run_id TEXT PRIMARY KEY, episode_id TEXT NOT NULL,
  intent_id TEXT NOT NULL REFERENCES intents(intent_id),
  contract_id TEXT NOT NULL, contract_version INTEGER NOT NULL,
  skill TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('DRAFT','READY','ACTIVE','WAITING_EVIDENCE','VERIFIED','FAILED','PARKED','ABORTED')),
  simulated INTEGER NOT NULL CHECK(simulated IN (0,1)),
  created_at TEXT NOT NULL, started_at TEXT,
  idempotency_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
  FOREIGN KEY(contract_id, contract_version) REFERENCES completion_contracts(contract_id, version)
);
CREATE TABLE IF NOT EXISTS action_steps (
  action_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES action_runs(run_id) ON DELETE CASCADE,
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES action_runs(run_id) ON DELETE CASCADE,
  criterion_id TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS outcomes (
  run_id TEXT PRIMARY KEY REFERENCES action_runs(run_id) ON DELETE CASCADE,
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS judgment_snapshots (
  snapshot_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES action_runs(run_id) ON DELETE CASCADE,
  recorded_at TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS learned_rules (
  rule_id TEXT PRIMARY KEY, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS rule_sources (
  rule_id TEXT NOT NULL REFERENCES learned_rules(rule_id) ON DELETE CASCADE,
  run_id TEXT NOT NULL REFERENCES action_runs(run_id) ON DELETE CASCADE,
  PRIMARY KEY(rule_id, run_id)
);
CREATE TABLE IF NOT EXISTS repeat_clusters (
  cluster_id TEXT PRIMARY KEY, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS repeat_members (
  cluster_id TEXT NOT NULL REFERENCES repeat_clusters(cluster_id) ON DELETE CASCADE,
  run_id TEXT NOT NULL REFERENCES action_runs(run_id) ON DELETE CASCADE,
  PRIMARY KEY(cluster_id, run_id)
);
CREATE TABLE IF NOT EXISTS skill_versions (
  version_id TEXT PRIMARY KEY, skill TEXT NOT NULL, version TEXT NOT NULL,
  artifact_sha256 TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('DRAFT','CANDIDATE','CANARY','STABLE','DEPRECATED','ROLLED_BACK')),
  payload TEXT NOT NULL CHECK(json_valid(payload)), UNIQUE(skill, version)
);
CREATE TABLE IF NOT EXISTS eval_cases (
  case_id TEXT PRIMARY KEY, split TEXT NOT NULL CHECK(split IN ('dev','holdout_candidate','sealed_holdout')),
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS eval_runs (
  eval_run_id TEXT PRIMARY KEY, version_id TEXT REFERENCES skill_versions(version_id),
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE TABLE IF NOT EXISTS trace_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL REFERENCES action_runs(run_id) ON DELETE CASCADE,
  timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS trace_run_idx ON trace_events(run_id,seq);
CREATE INDEX IF NOT EXISTS evidence_run_idx ON evidence(run_id);
PRAGMA user_version = 1;
