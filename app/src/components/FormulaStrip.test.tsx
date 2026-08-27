import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { FormulaStrip } from "@/components/FormulaStrip";
import type { DutyStack, Layer, Operator, Term } from "@/lib/types";

afterEach(cleanup);

function term(operator: Operator, ad_valorem_pct: string | null): Term {
  return { operator, text: "", ad_valorem_pct, specific_amount: null,
           specific_unit: null, amount_usd: null };
}

function layer(hts: string, operator: Operator, pct: string): Layer {
  return {
    hts, description: "", origin_scope: "none", cumulation: "in_lieu", conditions: [],
    scope: "by_code", term: term(operator, pct),
    effectivity: { status: "in_force", status_note: null, effective_from: null,
                   effective_to: null, standing: "in_force" },
    programme: null, evidence: [], countries: [], cas_numbers: [], cited_notes: [],
    excluded_by: [], coverage: null,
  };
}

function stack(over: Partial<DutyStack> = {}): DutyStack {
  return {
    query: { hts: "7208.51.00.30", country: "CN", country_name: "China",
             on_date: "2026-08-27", declared_value_usd: "100000", quantity: null,
             quantity_unit: null },
    classification: { hts: "7208.51.00.30", description: "", full_description: "",
                      units: [], chain: [] },
    base_rate: { column: "1-general", term: term("base", "0"), inherited_from: null,
                 special_text: null },
    column2: null, layers: [], origin_scoped: [], origin_unresolved: [], not_eligible: [],
    competing_replacements: [], reductions: [], exclusions: [], inactive: [],
    total: { expression: "Free", ad_valorem_pct: "0", specific_terms: [],
             amount_usd: "0.00", assumption: "Assumed.", ceiling_expression: null,
             ceiling_ad_valorem_pct: null, ceiling_amount_usd: null, ceiling_note: null },
    unknowns: [],
    ...over,
  };
}

const TWENTY_EXCLUSIONS = Array.from({ length: 4 }, (_, group) => ({
  note_label: `U.S. note 20(${group})`, note_id: group,
  provisions: Array.from({ length: 5 }, (_, n) => `9903.88.${group}${n}`),
}));

function calculation() {
  return within(screen.getByRole("group", { name: "Duty calculation" }));
}

test("the calculation carries no exclusion term, because no exclusion was calculated", () => {
  render(<FormulaStrip stack={stack({ exclusions: TWENTY_EXCLUSIONS })} />);

  expect(calculation().queryByText(/exclusion/i)).toBeNull();
});

test("the calculation carries no duty-reduction term either, for the same reason", () => {
  // combine() is never handed the reductions, so drawing one as a term claims an arithmetic
  // role it does not have -- the same false claim the exclusion cell was making.
  render(<FormulaStrip stack={stack({ reductions: [layer("9902.05.84", "replace", "0")] })} />);

  expect(calculation().queryByText(/reduction/i)).toBeNull();
});

test("exclusions are counted under the calculation, linked to the list further down", () => {
  render(<FormulaStrip stack={stack({ exclusions: TWENTY_EXCLUSIONS })} />);

  const link = screen.getByRole("link", { name: /20 possible product exclusions/i });
  expect(link.getAttribute("href")).toBe("#exclusions");
});

test("a shipment with no exclusions is told nothing about exclusions", () => {
  render(<FormulaStrip stack={stack()} />);

  expect(screen.queryByText(/exclusion/i)).toBeNull();
});

test("the calculation names its three parts rather than running the rates together", () => {
  render(<FormulaStrip stack={stack({
    layers: [layer("9903.91.01", "add", "25")],
    total: { ...stack().total, expression: "25%", ad_valorem_pct: "25",
             amount_usd: "25000.00" },
  })} />);

  const parts = calculation();
  expect(parts.getByText("Base rate")).toBeTruthy();
  expect(parts.getByText("Chapter 99 adjustments")).toBeTruthy();
  expect(parts.getByText("Estimated exposure")).toBeTruthy();
});

test("with nothing from Chapter 99 the calculation is base and result, not a dangling arrow", () => {
  const { container } = render(<FormulaStrip stack={stack()} />);

  expect(calculation().queryByText("Chapter 99 adjustments")).toBeNull();
  expect(calculation().getByText("Base rate")).toBeTruthy();
  expect(calculation().getByText("Estimated exposure")).toBeTruthy();
  expect(container.textContent).not.toContain("→");
});
