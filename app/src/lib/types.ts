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
