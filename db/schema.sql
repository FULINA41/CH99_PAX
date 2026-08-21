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
