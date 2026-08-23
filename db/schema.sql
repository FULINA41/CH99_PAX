-- Chapter 99 — starting schema.
--
-- Script to seed database schema. Add columns, tables, etc as needed.
-- Should be runnable from a clean install. Should define the schema
-- needed for parts 1, 2, and 3.
--
-- Rerunnable: it drops what it creates first, so applying it twice is safe.
-- Postgres has no CREATE OR REPLACE TABLE, so a clean schema means dropping.
-- That also means applying this wipes your parsed data; it is a schema reset,
-- not a migration.
--
--   ./setup.sh
--
-- Order matters on the way down: rule_edge references rule.

BEGIN;

DROP TABLE IF EXISTS rule_edge CASCADE;
DROP TABLE IF EXISTS rule CASCADE;
DROP TABLE IF EXISTS hts_base CASCADE;
DROP TABLE IF EXISTS source_fetch CASCADE;

-- One row per source per scraper run: where a payload came from, and when.
--
-- The HTSUS is revised several times a year and moved from Revision 15 to 16 during
-- this exercise, so the release is data rather than a constant. Recording it here is
-- what lets a parsed row be attributed to a revision.
--
-- 'unchanged' is not the same as 'fetched': it means the bytes were downloaded and
-- found identical to what was already on disk. Without that distinction a second run
-- looks like a no-op rather than a verification.
--
-- This duplicates data/raw/<release>/manifest.json on purpose. Applying this file is a
-- schema reset, so it wipes these rows; the manifest lives with the payloads and
-- survives. The manifest is authoritative when the two disagree.
CREATE TABLE source_fetch (
  id            bigserial PRIMARY KEY,
  run_id        text,
  source_key    text NOT NULL,
  release_name  text NOT NULL,
  release_title text,
  url           text NOT NULL,
  path          text,
  status        text NOT NULL
    CHECK (status IN ('fetched','unchanged','skipped','failed')),
  http_status   int,
  bytes         bigint,
  sha256        text,
  duration_ms   int,
  error         text,
  fetched_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX source_fetch_lookup_idx
  ON source_fetch (release_name, source_key, fetched_at DESC);

-- Chapters 1-97: what Chapter 99 points back at.
CREATE TABLE hts_base (
  hts          text PRIMARY KEY,
  description  text,
  mfn_rate_pct numeric
);

-- Chapter 99 provisions. rate_kind is the operator, rate_value the operand:
-- 'additive' with 25 means "base rate + 25", which a single numeric column
-- could not express.
CREATE TABLE rule (
  hts         text PRIMARY KEY,
  subchapter  text NOT NULL,
  description text NOT NULL,
  rate_kind   text NOT NULL
    CHECK (rate_kind IN ('free','additive','ad_valorem','no_change','specific','other')),
  rate_value  numeric,
  note_ref    text
);

-- The two relationships Chapter 99 states in prose.
--
-- target_hts is deliberately not a foreign key: a provision can name a base
-- code that no longer exists in the current revision, and those are worth
-- recording rather than dropping.
CREATE TABLE rule_edge (
  source_hts text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  edge_type  text NOT NULL CHECK (edge_type IN ('references','excludes')),
  target_hts text NOT NULL,
  PRIMARY KEY (source_hts, edge_type, target_hts)
);

CREATE INDEX rule_edge_target_idx ON rule_edge (target_hts, edge_type);

COMMIT;
