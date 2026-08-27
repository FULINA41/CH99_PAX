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

function Cell({
  sign, tone, value, label, lines, href,
}: {
  sign: string; tone: string; value: string; label: string; lines: string[]; href?: string;
}) {
  const head = (
    <span className={`font-mono text-2xl font-medium tabular ${tone}`}>
      {sign && <span aria-hidden className="mr-1">{sign}</span>}
      {value}
    </span>
  );
  return (
    <div className="min-w-[8.5rem] flex-1 border-t-2 border-rule pt-2 first:border-rule-strong">
      {href ? <a href={href} className="hover:underline">{head}</a> : head}
      <div className="mt-1 font-mono text-xs text-muted">{label}</div>
      {lines.map((line) => (
        <div key={line} className="text-xs leading-snug text-faint">{line}</div>
      ))}
    </div>
  );
}

export function FormulaStrip({ stack }: { stack: DutyStack }) {
  const { base_rate: base, total } = stack;
  const cells = [
    <Cell
      key="base"
      sign="" tone="text-ink"
      value={rate(base.term)}
      label={base.column === "2" ? "Column 2" : "Column 1 General"}
      lines={[
        base.inherited_from ? `inherited from ${base.inherited_from}` : "stated on this line",
        ...(base.column === "2" ? ["no normal trade relations"] : []),
      ]}
    />,
  ];

  // Only what the total is actually made of. The reductions never reach combine(), so a
  // reduction drawn as a term between the base and the "=" is an operand the figure never
  // used -- and a code carrying 34 of them drew 34 of those.
  for (const layer of stack.layers) {
    const mark = MARKS[layer.term.operator];
    cells.push(
      <Cell
        key={layer.hts}
        sign={mark.sign} tone={mark.tone}
        value={rate(layer.term)}
        label={layer.hts}
        lines={[layer.programme?.label ?? mark.note]}
        href={`#${layer.hts}`}
      />,
    );
  }

  if (stack.reductions.length > 0) {
    cells.push(
      <Cell
        key="reductions" sign="±" tone="text-flat" value="0"
        label={`${stack.reductions.length} duty reduction${
          stack.reductions.length === 1 ? "" : "s"}`}
        lines={["could stand in for the base rate", "if your goods are the ones named"]}
        href="#reductions"
      />,
    );
  }

  const excluded = stack.exclusions.reduce((n, g) => n + g.provisions.length, 0);
  if (excluded > 0) {
    cells.push(
      <Cell
        key="exclusions" sign="±" tone="text-flat" value="0"
        label={`${excluded} exclusions`}
        lines={["could remove one of the duties above", "if your goods are on the list"]}
        href="#exclusions"
      />,
    );
  }

  return (
    <section aria-label="How the duty is worked out" className="mt-8">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-5">
        {cells}
        <div className="min-w-[10rem] flex-1 border-t-2 border-ink pt-2">
          <div className="font-mono text-2xl font-semibold tabular text-ink">
            <span aria-hidden className="mr-1 text-faint">=</span>
            {total.expression}
          </div>
          <div className="mt-1 font-mono text-xs text-muted">
            {total.amount_usd ? money(total.amount_usd) : "needs a declared value"}
          </div>
          {total.ceiling_expression && (
            <div className="text-xs leading-snug text-unsure">
              up to {total.ceiling_expression}
              {total.ceiling_amount_usd && ` · ${money(total.ceiling_amount_usd)}`}
            </div>
          )}
        </div>
      </div>

      <p className="mt-4 max-w-prose text-sm leading-relaxed text-muted">{total.assumption}</p>
      {total.ceiling_note && (
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">{total.ceiling_note}</p>
      )}
    </section>
  );
}

export { MARKS, rate };
export type { Layer };
