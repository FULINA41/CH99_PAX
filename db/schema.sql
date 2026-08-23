-- Chapter 99 — database schema.
--
-- Builds every table Parts 1, 2 and 3 need, from an empty database.
--
-- Rerunnable: it drops what it creates first, so applying it twice is safe.
-- Postgres has no CREATE OR REPLACE TABLE, so a clean schema means dropping.
-- That also means applying this wipes your parsed data; it is a schema reset,
-- not a migration.
--
--   ./setup.sh
--
-- The shape follows one principle: what a source *says* and what we *concluded*
-- from it are different layers, and they get different tables. rule_edge holds the
-- code a provision cites, verbatim and unresolved; rule_base_match holds the base
-- rows we decided that citation reaches. A reviewer can audit the interpretation
-- without re-reading the prose, and a wrong resolver can be rebuilt without
-- re-parsing. See docs/DECISIONS.md D-0015.
--
-- Three columns of the starting schema are gone and one CHECK vocabulary changed.
-- Every departure is recorded, with the original SQL, in DECISIONS.md D-0021.

BEGIN;

-- Trigram search over descriptions. Part 3 has to turn a product name a person
-- typed into candidate headings, and the schedule's wording is nothing like the
-- words people use. Ships with the stock postgres image; pgvector does not, which
-- is why nothing here depends on embeddings.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP TABLE IF EXISTS parse_issue CASCADE;
DROP TABLE IF EXISTS rule_base_match CASCADE;
DROP TABLE IF EXISTS note_subheading CASCADE;
DROP TABLE IF EXISTS rule_note CASCADE;
DROP TABLE IF EXISTS note CASCADE;
DROP TABLE IF EXISTS rule_country CASCADE;
DROP TABLE IF EXISTS rule_identifier CASCADE;
DROP TABLE IF EXISTS rule_edge CASCADE;
DROP TABLE IF EXISTS rule CASCADE;
DROP TABLE IF EXISTS hts_base CASCADE;
DROP TABLE IF EXISTS source_fetch CASCADE;


-- ===========================================================================
-- Provenance
-- ===========================================================================

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


-- ===========================================================================
-- The base schedule, chapters 1-97
-- ===========================================================================

-- One row per code. The 5,614 rows in the export that carry no code are heading
-- rows: not classifiable, and carrying no rate of any kind — verified, none of them
-- has general, other, special or additionalDuties. Their prose scopes their children
-- and is preserved on every descendant in full_description rather than as rows of its
-- own. D-0012.
--
-- rate_kind is an operator and the three columns beside it are its operands, so a
-- rate can be computed rather than only shown. D-0013:
--
--   'Free'              free      pct=0
--   '2.5%'              replace   pct=2.5
--   '14.27c/liter'      replace   amount=14.27  unit='liter'
--   '4.4c/kg + 8.5%'    replace   amount=4.4    unit='kg'    pct=8.5
--   a sentence          prose     nothing computable; rate_text holds the words
--
-- 'free' is 'replace' with pct 0, kept separate only because the schedule writes it
-- as a word: a calculation may ignore the distinction, a display should not.
CREATE TABLE hts_base (
  hts                  text PRIMARY KEY,
  -- Nearest ancestor that carries a code. Rebuilt from indent, then checked against
  -- the code itself: a parent's code must be a dotted prefix of its child's.
  parent_hts           text REFERENCES hts_base(hts) ON DELETE SET NULL,
  indent               int  NOT NULL,
  description          text NOT NULL,
  -- The ancestor chain joined onto the row's own prose. "Other" is meaningless
  -- alone; this is what the row actually covers, and what Part 3 searches.
  full_description     text NOT NULL,
  -- An array because 4,725 rows report two units, e.g. {doz.,kg}. Without it a
  -- specific duty like 15.4c/kg cannot be applied to a shipment.
  units                text[],

  -- Column 1 General: what a normal-trade-relations country pays.
  rate_text            text,
  rate_kind            text NOT NULL
    CHECK (rate_kind IN ('free','replace','additive','no_change','prose','none')),
  rate_ad_valorem_pct  numeric,
  rate_specific_amount numeric,
  rate_specific_unit   text,
  -- Which ancestor the rate came from; NULL when the row states its own. 20,446 of
  -- 31,860 rows inherit, and materialising keeps every duty lookup a single read.
  -- D-0014.
  rate_inherited_from  text REFERENCES hts_base(hts) ON DELETE SET NULL,

  -- Column 2: countries without normal trade relations. Eightfold higher than
  -- Column 1 on the same line, so it is parsed rather than only stored.
  col2_rate_text       text,
  col2_rate_kind       text
    CHECK (col2_rate_kind IN ('free','replace','additive','no_change','prose','none')),
  col2_ad_valorem_pct  numeric,
  col2_specific_amount numeric,
  col2_specific_unit   text,

  -- Column 1 Special, as printed. Decoding 'A+', 'KR', 'AU' needs the HTS General
  -- Notes, which none of the three sources contains — see DATA_INVENTORY.md 5.
  special_text         text,

  source_fetch_id      bigint REFERENCES source_fetch(id) ON DELETE SET NULL,

  full_description_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(full_description, ''))) STORED
);

CREATE INDEX hts_base_parent_idx ON hts_base (parent_hts);
CREATE INDEX hts_base_fts_idx    ON hts_base USING gin (full_description_tsv);
CREATE INDEX hts_base_trgm_idx   ON hts_base USING gin (full_description gin_trgm_ops);


-- ===========================================================================
-- Chapter 99 provisions
-- ===========================================================================

-- The same rate model as hts_base, plus the two things Chapter 99 adds: operators
-- that are relative to the base rate ('additive', 'no_change'), and a scope.
--
-- scope exists because 358 provisions name a country and no base code of their own
-- ("articles the product of Mexico"). Those have no join key to the base schedule, and
-- a resolver that only follows code citations drops them silently — along with the most
-- frequently applied duties in the current schedule. D-0018. How many end up in each
-- scope is settled by the resolver, since a note citation only reaches base codes when
-- that note is a list of subheadings.
CREATE TABLE rule (
  hts         text PRIMARY KEY,
  heading     text NOT NULL,
  -- Roman numeral, derived: the heading's last two digits are the subchapter number
  -- (9915 -> XV). Not stated in the JSON, but exact.
  subchapter  text NOT NULL,
  parent_hts  text REFERENCES rule(hts) ON DELETE SET NULL,
  indent      int  NOT NULL,
  description text NOT NULL,
  full_description text NOT NULL,
  scope       text NOT NULL
    CHECK (scope IN ('by_code','by_country_all_goods','unknown')),

  rate_text            text,
  rate_kind            text NOT NULL
    CHECK (rate_kind IN ('free','replace','additive','no_change','prose','none')),
  rate_ad_valorem_pct  numeric,
  rate_specific_amount numeric,
  rate_specific_unit   text,

  -- A second duty stacked on top of rate_*, always additive. 512 provisions carry
  -- one; 50 of those read "No additional duty", which is a stated zero rather than a
  -- missing value, so the text is kept beside the parsed operands.
  additional_duty_text   text,
  additional_duty_pct    numeric,
  additional_duty_amount numeric,
  additional_duty_unit   text,

  source_fetch_id bigint REFERENCES source_fetch(id) ON DELETE SET NULL,

  full_description_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(full_description, ''))) STORED
);

CREATE INDEX rule_scope_idx  ON rule (scope);
CREATE INDEX rule_parent_idx ON rule (parent_hts);
CREATE INDEX rule_fts_idx    ON rule USING gin (full_description_tsv);
CREATE INDEX rule_trgm_idx   ON rule USING gin (full_description gin_trgm_ops);


-- What a provision says, before anyone decides what it means.
--
-- target_hts is deliberately not a foreign key and deliberately not normalised: it
-- is the string as printed, usually an 8-digit subheading matching no row in
-- hts_base, and sometimes a code that no longer exists in this revision. Both are
-- worth recording rather than dropping. rule_base_match holds the resolution.
CREATE TABLE rule_edge (
  source_hts text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  edge_type  text NOT NULL CHECK (edge_type IN ('references','excludes')),
  target_hts text NOT NULL,
  PRIMARY KEY (source_hts, edge_type, target_hts)
);

CREATE INDEX rule_edge_target_idx ON rule_edge (target_hts, edge_type);


-- Which goods a provision is about, when the HTS code cannot say.
--
-- 51% of the base codes Chapter 99 cites are cited by more than one provision;
-- 3808.92.15 is cited by 34. Four provisions cite 2922.49.30, each naming a
-- different substance by CAS number. The classification does not choose between
-- them — the identity of the goods does, and that identity is only in the prose.
-- 1,034 provisions carry a CAS registry number, exact and globally unique. D-0019.
CREATE TABLE rule_identifier (
  rule_hts text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  kind     text NOT NULL CHECK (kind IN ('cas')),
  value    text NOT NULL,
  PRIMARY KEY (rule_hts, kind, value)
);

CREATE INDEX rule_identifier_value_idx ON rule_identifier (kind, value);


-- Country of origin, the dimension subchapter III keys on. Many-to-many: one
-- provision can name several countries, and 'excluded' carries as much weight as
-- 'product_of' because reciprocal-tariff headings carve countries back out.
--
-- country_code is ISO 3166-1 alpha-2 where the name could be normalised and NULL
-- where it could not; the prose is kept either way.
CREATE TABLE rule_country (
  rule_hts     text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  country_name text NOT NULL,
  country_code text,
  relation     text NOT NULL CHECK (relation IN ('product_of','excluded')),
  PRIMARY KEY (rule_hts, country_name, relation)
);

CREATE INDEX rule_country_code_idx ON rule_country (country_code, relation);


-- ===========================================================================
-- U.S. notes, from the PDF
-- ===========================================================================

-- 973 provisions cite a U.S. note, across 35 distinct numbers, and many take their scope
-- from it rather than from codes they name. 9903.88.01 covers "the subheadings enumerated
-- in U.S. note 20(b)", and that list exists only in the PDF. D-0016.
--
-- The number alone does not identify a note: "U.S. note 2 to subchapter III" and
-- "additional U.S. note 2 to chapter 4" are different notes, which is why the unique key
-- below is the whole tuple and not note_number.
--
-- NULLS NOT DISTINCT so two chapter-level notes with no subdivision collide on the
-- unique key instead of both being inserted.
CREATE TABLE note (
  id           bigserial PRIMARY KEY,
  note_kind    text NOT NULL CHECK (note_kind IN ('chapter','us_note','statistical')),
  subchapter   text,
  note_number  text NOT NULL,
  subdivision  text,
  label        text NOT NULL,
  body         text NOT NULL,
  -- 'subheading_list' notes are pages of bare codes and get expanded into
  -- note_subheading; 'prose' notes are stored to be read, not parsed.
  content_kind text NOT NULL CHECK (content_kind IN ('prose','subheading_list','mixed')),
  page_from    int,
  page_to      int,
  source_fetch_id bigint REFERENCES source_fetch(id) ON DELETE SET NULL,
  UNIQUE NULLS NOT DISTINCT (note_kind, subchapter, note_number, subdivision)
);


-- A provision citing a note. cited_text is what the description said; note_id is
-- what it was matched to, and stays NULL when no note matched — an unresolved
-- citation keeps its text here and gets a parse_issue row, rather than vanishing.
CREATE TABLE rule_note (
  id         bigserial PRIMARY KEY,
  rule_hts   text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  cited_text text NOT NULL,
  note_id    bigint REFERENCES note(id) ON DELETE SET NULL,
  UNIQUE (rule_hts, cited_text)
);

CREATE INDEX rule_note_note_idx ON rule_note (note_id);


-- The codes printed inside a list-type note, in the order they appear. A fact layer
-- like rule_edge: 8-digit as printed, no resolution. rule_base_match derives from it.
CREATE TABLE note_subheading (
  note_id    bigint NOT NULL REFERENCES note(id) ON DELETE CASCADE,
  hts_prefix text   NOT NULL,
  ordinal    int    NOT NULL,
  PRIMARY KEY (note_id, hts_prefix)
);

CREATE INDEX note_subheading_prefix_idx ON note_subheading (hts_prefix);


-- ===========================================================================
-- The resolved layer
-- ===========================================================================

-- Which base rows a provision actually reaches, and how it got there.
--
-- Citations are 8-digit and base rows are 8 or 10, so matching is prefix matching
-- anchored at a separator; the expansion varies by three orders of magnitude
-- (2922.49.30 reaches 1 row, 4202 reaches 108), which is why it is materialised
-- rather than recomputed per query. Everything here is interpretation and can be
-- rebuilt from rule_edge and note_subheading alone. D-0015.
CREATE TABLE rule_base_match (
  rule_hts   text NOT NULL REFERENCES rule(hts) ON DELETE CASCADE,
  base_hts   text NOT NULL REFERENCES hts_base(hts) ON DELETE CASCADE,
  cited_code text NOT NULL,
  match_kind text NOT NULL CHECK (match_kind IN ('exact','prefix')),
  via        text NOT NULL CHECK (via IN ('description','note')),
  note_id    bigint REFERENCES note(id) ON DELETE SET NULL,
  PRIMARY KEY (rule_hts, base_hts, cited_code)
);

CREATE INDEX rule_base_match_base_idx ON rule_base_match (base_hts);


-- ===========================================================================
-- Honesty
-- ===========================================================================

-- Everything the parser could not turn into a row. A prose schedule always leaves
-- residue; the failure worth preventing is not having residue but losing it quietly,
-- so nothing is dropped without a row here. An empty table after a full run means
-- the parser is not looking, not that the data is clean. D-0017.
CREATE TABLE parse_issue (
  id         bigserial PRIMARY KEY,
  run_id     text,
  stage      text NOT NULL CHECK (stage IN ('base','ch99','notes','resolve')),
  issue_kind text NOT NULL,
  subject    text,
  detail     text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX parse_issue_kind_idx ON parse_issue (stage, issue_kind);

COMMIT;
