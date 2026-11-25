PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS storage_metadata (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL CHECK(json_valid(value_json))
);
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS occurrences (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  source_id TEXT REFERENCES sources(id) DEFERRABLE INITIALLY DEFERRED,
  claim_id TEXT REFERENCES claims(id) DEFERRABLE INITIALLY DEFERRED,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS review_votes (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  claim_id TEXT REFERENCES claims(id) DEFERRABLE INITIALLY DEFERRED,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  claim_id TEXT REFERENCES claims(id) DEFERRABLE INITIALLY DEFERRED,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS cost_events (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS source_access (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  source_id TEXT REFERENCES sources(id) DEFERRABLE INITIALLY DEFERRED,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE IF NOT EXISTS media_assets (
  id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
  source_id TEXT REFERENCES sources(id) DEFERRABLE INITIALLY DEFERRED,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE INDEX IF NOT EXISTS occurrences_source ON occurrences(source_id);
CREATE INDEX IF NOT EXISTS occurrences_claim ON occurrences(claim_id);
CREATE INDEX IF NOT EXISTS media_assets_source ON media_assets(source_id);
CREATE INDEX IF NOT EXISTS source_access_source ON source_access(source_id);
