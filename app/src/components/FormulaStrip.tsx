import type { DutyStack, Layer, Operator, Term } from "@/lib/types";
import { money } from "@/lib/types";

// Symbol and colour together, never colour alone. The mark is what carries the meaning; the
// colour only makes it faster to find.
const MARKS: Record<Operator, { sign: string; tone: string; note: string }> = {
  base: { sign: "", tone: "text-ink", note: "" },
  add: { sign: "+", tone: "text-raise", note: "adds to the base rate" },
  replace: { sign: "→", tone: "text-lower", note: "stands in for the base rate" },
  no_change: { sign: "±", tone: "text-flat", note: "changes nothing by itself" },
  unknown: { sign: "?", tone: "text-unsure", note: "stated in words, not computable" },
};

function rate(term: Term): string {
  if (term.operator === "unknown") return "?";
  if (term.operator === "no_change") return "0";
  const parts: string[] = [];
  if (term.ad_valorem_pct !== null) {
    parts.push(Number(term.ad_valorem_pct) === 0 ? "Free" : `${Number(term.ad_valorem_pct)}%`);
  }
  if (term.specific_amount !== null) {
    parts.push(`$${Number(term.specific_amount)}/${term.specific_unit ?? "unit"}`);
  }
  return parts.join(" + ") || term.text || "—";
}

// The three parts do not come from the same place and are not drawn as though they do: the
// base rate is one figure the schedule prints, the adjustments are a set of separate
// provisions, and the exposure is what this site worked out from them.
function Part({
  label, hint, tone, children,
}: { label: string; hint?: string; tone: string; children: React.ReactNode }) {
  return (
    <div className={`min-w-[9rem] flex-1 ${tone}`}>
      <h3 className="text-xs font-medium uppercase tracking-wide text-faint">{label}</h3>
      {hint && <div className="text-xs text-faint">{hint}</div>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Operator({ glyph }: { glyph: string }) {
  // The labels carry the relationship for a screen reader; the glyph only speeds up the eye.
  return (
    <div aria-hidden className="hidden self-center pt-5 font-mono text-xl text-faint sm:block">
      {glyph}
    </div>
  );
}

function Adjustment({ layer }: { layer: Layer }) {
  const mark = MARKS[layer.term.operator];
  return (
    <li>
      <a href={`#${layer.hts}`} className="group block">
        <span className={`font-mono text-2xl font-medium tabular ${mark.tone}`}>
          {mark.sign && <span aria-hidden className="mr-1">{mark.sign}</span>}
          {rate(layer.term)}
        </span>
        <span className="ml-2 font-mono text-xs text-muted group-hover:underline">
          {layer.hts}
        </span>
      </a>
      <div className="text-xs leading-snug text-faint">
        {layer.programme?.label ?? mark.note}
      </div>
    </li>
  );
}

// Everything the figure deliberately left out. Each says what it is, how many, and where the
// page answers it -- an exclusion is a claim about the goods, and no count of HTS matches
// decides it.
function NotCounted({ stack }: { stack: DutyStack }) {
  const excluded = stack.exclusions.reduce((n, group) => n + group.provisions.length, 0);
  const reduced = stack.reductions.length;
  if (excluded === 0 && reduced === 0) return null;

  return (
    <div className="mt-6 border-l-2 border-rule-strong pl-4">
      <h3 className="text-xs font-medium uppercase tracking-wide text-faint">
        Not included in this calculation
      </h3>
      <ul className="mt-2 space-y-3">
        {excluded > 0 && (
          <li>
            <a
              href="#exclusions"
              className="text-ink underline decoration-rule-strong underline-offset-2
                         hover:decoration-ink"
            >
              {excluded} possible product exclusion{excluded === 1 ? "" : "s"}
            </a>
            <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted">
              These exclusions are not included in the calculation. An HTS match only
              identifies possible exclusions; whether one applies depends on the specific
              goods and the relevant U.S. note.
            </p>
          </li>
        )}
        {reduced > 0 && (
          <li>
            <a
              href="#reductions"
              className="text-ink underline decoration-rule-strong underline-offset-2
                         hover:decoration-ink"
            >
              {reduced} possible duty reduction{reduced === 1 ? "" : "s"}
            </a>
            <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted">
              Alternatives to the base rate rather than additions to it, so they are not in
              the figure either. Which one applies, if any, depends on what the goods are.
            </p>
          </li>
        )}
      </ul>
    </div>
  );
}

export function FormulaStrip({ stack }: { stack: DutyStack }) {
  const { base_rate: base, total } = stack;
  const adjusted = stack.layers.length > 0;

  return (
    <section aria-label="How the duty is worked out" className="mt-8">
      <div
        role="group" aria-label="Duty calculation"
        className="flex flex-wrap items-stretch gap-x-4 gap-y-6"
      >
        <Part
          label="Base rate" hint="Chapters 1&ndash;97"
          tone="border-t-2 border-rule-strong pt-2"
        >
          <span className="font-mono text-2xl font-medium tabular text-ink">
            {rate(base.term)}
          </span>
          <div className="mt-1 text-xs text-muted">
            {base.column === "2" ? "Column 2" : "Column 1 General"}
          </div>
          <div className="text-xs leading-snug text-faint">
            {base.inherited_from ? `inherited from ${base.inherited_from}` : "stated on this line"}
          </div>
          {base.column === "2" && (
            <div className="text-xs leading-snug text-faint">no normal trade relations</div>
          )}
        </Part>

        {adjusted && <Operator glyph="&rarr;" />}

        {adjusted && (
          <Part
            label="Chapter 99 adjustments"
            hint={`${stack.layers.length} provision${stack.layers.length === 1 ? "" : "s"}`}
            tone="rounded-sm border border-rule-strong bg-raised px-3 pb-3 pt-2"
          >
            <ul className="space-y-3">
              {stack.layers.map((layer) => <Adjustment key={layer.hts} layer={layer} />)}
            </ul>
          </Part>
        )}

        <Operator glyph="=" />

        <Part label="Estimated exposure" tone="border-t-2 border-ink pt-2">
          <span className="font-mono text-2xl font-semibold tabular text-ink">
            {total.expression}
          </span>
          <div className={`mt-1 text-xs text-muted ${
            total.amount_usd ? "font-mono tabular" : ""}`}>
            {total.amount_usd ? money(total.amount_usd) : "needs a declared value"}
          </div>
          {total.ceiling_expression && (
            <div className="text-xs leading-snug text-unsure">
              up to {total.ceiling_expression}
              {total.ceiling_amount_usd && ` · ${money(total.ceiling_amount_usd)}`}
            </div>
          )}
        </Part>
      </div>

      <NotCounted stack={stack} />

      <p className="mt-4 max-w-prose text-sm leading-relaxed text-muted">{total.assumption}</p>
      {total.ceiling_note && (
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">{total.ceiling_note}</p>
      )}
    </section>
  );
}

export { MARKS, rate };
export type { Layer };
