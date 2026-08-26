import { MARKS, rate } from "@/components/FormulaStrip";
import type { Layer } from "@/lib/types";

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 text-sm">
      <dt className="w-32 shrink-0 text-faint">{label}</dt>
      <dd className="text-muted">{children}</dd>
    </div>
  );
}

const STANDING: Record<string, string> = {
  not_yet: "Not in force on this date",
  expired: "No longer in force on this date",
  stopped: "Stopped",
  in_force: "",
};

export function LayerCard({ layer, dimmed = false }: { layer: Layer; dimmed?: boolean }) {
  const mark = MARKS[layer.term.operator];
  const { effectivity: when } = layer;
  const widened = layer.evidence.some((e) => e.note_precision === "parent_fallback");

  return (
    <article
      id={layer.hts}
      className={`border-t border-rule py-6 scroll-mt-6 ${dimmed ? "opacity-70" : ""}`}
    >
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <a
          href={`/rule/${layer.hts}`}
          className="font-mono text-lg font-medium text-ink underline decoration-rule-strong
                     underline-offset-4 hover:decoration-ink"
        >
          {layer.hts}
        </a>
        <span className={`font-mono text-lg font-medium tabular ${mark.tone}`}>
          {mark.sign && <span aria-hidden className="mr-1">{mark.sign}</span>}
          {rate(layer.term)}
        </span>
        {layer.programme && (
          <span className="rounded-sm bg-raised px-2 py-0.5 text-xs text-muted">
            {layer.programme.label}
            <span className="ml-1.5 text-faint">· editorial</span>
          </span>
        )}
        {STANDING[when.standing] && (
          <span className="rounded-sm bg-unsure-soft px-2 py-0.5 text-xs text-unsure">
            {STANDING[when.standing]}
          </span>
        )}
      </header>

      <p className="mt-3 max-w-prose text-[0.95rem] leading-relaxed text-ink">
        {layer.description}
      </p>

      <div className="mt-4">
        <h4 className="text-xs font-medium uppercase tracking-wide text-faint">
          Why this is in your answer
        </h4>
        <ul className="mt-2 space-y-1.5">
          {layer.evidence.map((item, index) => (
            <li
              key={index}
              className={`max-w-prose text-sm leading-relaxed ${
                item.note_precision === "parent_fallback" ? "text-unsure" : "text-muted"
              }`}
            >
              <span aria-hidden className="mr-2 text-faint">·</span>
              {item.detail}
              {item.note_id && (
                <>
                  {" "}
                  <a
                    className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                    href={`/note/${item.note_id}`}
                  >
                    read {item.note_label}
                  </a>
                  {item.note_page && (
                    <span className="text-faint"> · PDF page {item.note_page}</span>
                  )}
                </>
              )}
            </li>
          ))}
          {layer.evidence.length === 0 && (
            <li className="max-w-prose text-sm text-muted">
              <span aria-hidden className="mr-2 text-faint">·</span>
              Matched on country of origin alone.
            </li>
          )}
        </ul>
      </div>

      {layer.conditions.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {layer.conditions.map((condition) => (
            <li key={condition.verbatim} className="max-w-prose text-sm leading-relaxed">
              <span aria-hidden className="mr-2 text-faint">·</span>
              <span className={condition.met === false ? "text-unsure" : "text-muted"}>
                {condition.met === false
                  ? "Its own text rules these goods out: "
                  : condition.met === null
                    ? "States a condition this base rate cannot be judged against: "
                    : "Condition met: "}
              </span>
              <span className="italic text-ink">&ldquo;{condition.verbatim}&rdquo;</span>
            </li>
          ))}
        </ul>
      )}

      <dl className="mt-4 space-y-1">
        {when.effective_from && (
          <Meta label="In force from">{when.effective_from}</Meta>
        )}
        {when.effective_to && <Meta label="Last day in force">{when.effective_to}</Meta>}
        {when.status_note && (
          <Meta label="Compiler's note">
            <span className="italic">{when.status_note}</span>
          </Meta>
        )}
        {layer.countries.length > 0 && (
          <Meta label="Names">{layer.countries.join(", ")}</Meta>
        )}
        {layer.cas_numbers.length > 0 && (
          <Meta label="CAS numbers">
            <span className="font-mono">{layer.cas_numbers.join(", ")}</span>
          </Meta>
        )}
        {layer.coverage !== null && (
          <Meta label="Reaches">
            {layer.coverage.toLocaleString()} base codes
            {widened && (
              <span className="text-unsure">
                {" "}— wider than the provision, see above
              </span>
            )}
          </Meta>
        )}
        {layer.excluded_by.length > 0 && (
          <Meta label="Carve-outs">
            {layer.excluded_by.length} headings can remove this duty:{" "}
            {layer.excluded_by.slice(0, 6).map((hts, index) => (
              <span key={hts}>
                {index > 0 && ", "}
                <a href={`/rule/${hts}`} className="font-mono text-xs underline
                   decoration-rule-strong underline-offset-2 hover:decoration-ink">{hts}</a>
              </span>
            ))}
            {layer.excluded_by.length > 6 && ` and ${layer.excluded_by.length - 6} more`}
          </Meta>
        )}
      </dl>
    </article>
  );
}
