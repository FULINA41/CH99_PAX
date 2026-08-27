// Mirrors api/models.py. Hand-written rather than generated: the API's OpenAPI document is
// the contract, and one file of types is cheaper to read than a generator in the build.

export type Operator = "base" | "add" | "replace" | "no_change" | "unknown";
export type Standing = "in_force" | "not_yet" | "expired" | "stopped";
export type Precision = "exact" | "parent_fallback" | "chapter_note" | "unresolved";

export type Term = {
  operator: Operator;
  text: string;
  ad_valorem_pct: string | null;
  specific_amount: string | null;
  specific_unit: string | null;
  amount_usd: string | null;
};

export type Programme = {
  heading_prefix: string;
  label: string;
  statute: string;
  agency: string;
  evidence: string;
  reference_url: string;
  editorial: true;
};

export type Condition = {
  kind: "col1_rate";
  operator: "lt" | "gte";
  value: string;
  verbatim: string;
  // null when the base rate is a sentence, so the condition can be neither met nor failed.
  met: boolean | null;
};

export type Evidence = {
  kind: "cited_code" | "note_list" | "country" | "country_wide";
  detail: string;
  cited_code: string | null;
  match_kind: "exact" | "prefix" | null;
  note_id: number | null;
  note_label: string | null;
  note_page: number | null;
  note_precision: Precision | null;
};

export type CitedNote = {
  note_id: number | null;
  label: string | null;
  cited_text: string;
  cited_subdivision: string | null;
  page_from: number | null;
  precision: Precision;
};

export type Effectivity = {
  status: "in_force" | "terminated" | "suspended";
  status_note: string | null;
  effective_from: string | null;
  effective_to: string | null;
  standing: Standing;
};

export type Layer = {
  hts: string;
  description: string;
  origin_scope: "none" | "any" | "named" | "unresolved";
  cumulation: "in_lieu" | "cumulative" | "unstated";
  conditions: Condition[];
  scope: "by_code" | "by_country_all_goods" | "unknown";
  term: Term;
  effectivity: Effectivity;
  programme: Programme | null;
  evidence: Evidence[];
  countries: string[];
  cas_numbers: string[];
  cited_notes: CitedNote[];
  excluded_by: string[];
  coverage: number | null;
};

export type BaseRate = {
  column: "1-general" | "2";
  term: Term;
  inherited_from: string | null;
  special_text: string | null;
};

export type Unknown = {
  question: string;
  why: string;
  source_name: string;
  url: string;
  what_to_search: string;
  related_hts: string[];
};

export type DutyStack = {
  query: {
    hts: string;
    country: string | null;
    country_name: string | null;
    on_date: string;
    declared_value_usd: string | null;
    quantity: string | null;
    quantity_unit: string | null;
  };
  classification: {
    hts: string;
    description: string;
    full_description: string;
    units: string[];
    chain: string[];
  };
  base_rate: BaseRate;
  column2: BaseRate | null;
  layers: Layer[];
  origin_scoped: Layer[];
  origin_unresolved: Layer[];
  not_eligible: Layer[];
  competing_replacements: Layer[];
  reductions: Layer[];
  exclusions: { note_label: string | null; note_id: number | null; provisions: string[] }[];
  inactive: Layer[];
  total: {
    expression: string;
    ad_valorem_pct: string | null;
    specific_terms: string[];
    amount_usd: string | null;
    assumption: string;
    ceiling_expression: string | null;
    ceiling_ad_valorem_pct: string | null;
    ceiling_amount_usd: string | null;
    ceiling_note: string | null;
  };
  unknowns: Unknown[];
};

export const money = (value: string | null): string | null =>
  value === null ? null : `$${Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`;

export type Countries = {
  named: { country_code: string; name: string; provisions: number }[];
  all: { country_code: string; name: string; named_by_chapter_99: boolean }[];
};

export type RuleDetail = {
  rule: {
    hts: string; heading: string; subchapter: string; full_description: string;
    scope: string; rate_text: string | null; rate_kind: string;
    rate_kind_reading: string; scope_reading: string; status_reading: string;
    rate_ad_valorem_pct: string | null; rate_specific_amount: string | null;
    rate_specific_unit: string | null; additional_duty_text: string | null;
    effective_from: string | null; effective_to: string | null;
    status: string; status_note: string | null;
    base_codes: number | null; direct_codes: number | null; note_codes: number | null;
    label: string | null; statute: string | null; agency: string | null;
    evidence: string | null; reference_url: string | null;
  };
  cited_codes: { cited_code: string; reaches: number }[];
  notes: {
    cited_text: string; cited_subdivision: string | null; match_precision: Precision;
    note_id: number | null; label: string | null; content_kind: string | null;
    page_from: number | null; page_to: number | null; listed_codes: number;
  }[];
  countries: { country_name: string; country_code: string | null; relation: string }[];
  identifiers: { kind: string; value: string }[];
  carves_out: { target_hts: string; source_hts: string; description: string | null; rate_text: string | null }[];
  carved_out_by: { target_hts: string; source_hts: string; description: string | null; rate_text: string | null }[];
  sample: { base_hts: string; cited_code: string; match_kind: string; path: string;
            how: string }[];
};

export type NoteDetail = {
  note: {
    id: number; label: string; note_kind: string; subchapter: string | null;
    note_number: string; subdivision: string | null; body: string;
    content_kind: string; page_from: number | null; page_to: number | null;
    listed_codes: number;
  };
  codes: { hts_prefix: string; ordinal: number; reaches: number }[];
  codes_offset: number;
  family: { id: number; label: string; subdivision: string | null; content_kind: string; listed_codes: number }[];
  citing: {
    rule_hts: string; cited_text: string; cited_subdivision: string | null;
    match_precision: Precision; rate_text: string | null; rate_kind: string;
    status: string; description: string; programme: string | null;
  }[];
};
