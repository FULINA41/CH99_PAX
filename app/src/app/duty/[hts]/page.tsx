import { notFound } from "next/navigation";

import { FormulaStrip } from "@/components/FormulaStrip";
import { LayerCard } from "@/components/LayerCard";
import { Unknowns } from "@/components/Unknowns";
import { api } from "@/lib/api";
import type { Countries, DutyStack, Layer } from "@/lib/types";

// Country is a query parameter, not a path segment, so a plain GET form can change it -- a
// <select> and a submit button, no JavaScript, and the URL stays shareable.
type Params = Promise<{ hts: string }>;
type Search = Promise<{ country?: string; value?: string; quantity?: string; on?: string }>;

function Section({
  id, title, blurb, children,
}: { id: string; title: string; blurb: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mt-12 scroll-mt-6">
      <h2 className="font-serif text-xl text-ink">{title}</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">{blurb}</p>
      {children}
    </section>
  );
}

function Collapsed({
  summary, blurb, children,
}: { summary: string; blurb: string; children: React.ReactNode }) {
  return (
    <details className="mt-12 border-t border-rule pt-4">
      <summary className="font-serif text-xl text-ink">{summary}</summary>
      <p className="ml-4 mt-1 max-w-prose text-sm text-muted">{blurb}</p>
      <div className="ml-4">{children}</div>
    </details>
  );
}

export default async function DutyPage(
  { params, searchParams }: { params: Params; searchParams: Search },
) {
  const { hts } = await params;
  const { country, value, quantity, on } = await searchParams;

  const query = new URLSearchParams();
  if (country) query.set("country", country);
  if (value) query.set("value", value);
  if (quantity) query.set("quantity", quantity);
  if (on) query.set("on", on);

  let stack: DutyStack;
  let countries: Countries;
  try {
    [stack, countries] = await Promise.all([
      api<DutyStack>(`/duty/${hts}?${query}`),
      api<Countries>("/countries"),
    ]);
  } catch {
    notFound();
  }

  const { classification: good, query: asked } = stack;
  const jsonPath = `/api/duty/${hts}?${query}`;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <a href="/" className="text-xs text-faint hover:text-muted">← Chapter 99</a>

      <header className="mt-6">
        <p className="text-xs uppercase tracking-wide text-faint">
          Classified good · chapters 1&ndash;97
        </p>
        <h1 className="mt-1 font-mono text-3xl font-medium tracking-tight text-ink">
          {good.hts}
        </h1>
        <p className="mt-3 max-w-prose text-[0.95rem] leading-relaxed text-ink">
          {good.full_description}
        </p>
        <p className="mt-3 text-sm text-muted">
          Product of{" "}
          <span className="text-ink">{asked.country_name ?? "— no country stated —"}</span>
          {asked.declared_value_usd && (
            <> · declared value{" "}
              <span className="tabular text-ink">
                ${Number(asked.declared_value_usd).toLocaleString()}
              </span>
            </>
          )}
          {" "}· judged on <span className="tabular text-ink">{asked.on_date}</span>
          {good.units.length > 0 && (
            <span className="text-faint"> · reported in {good.units.join(", ")}</span>
          )}
        </p>
      </header>

      <FormulaStrip stack={stack} />

      <form className="mt-8 flex flex-wrap items-end gap-4 border-t border-rule pt-6" action="">
        <label className="text-sm">
          <span className="block text-xs text-faint">Country of origin</span>
          <select
            name="country" defaultValue={country ?? ""}
            className="mt-1 w-52 border-b border-rule-strong bg-transparent py-1 text-ink
                       outline-none focus:border-ink"
          >
            <option value="">— not stated —</option>
            <optgroup label="Named by Chapter 99">
              {countries.named.map((c) => (
                <option key={c.country_code} value={c.country_code}>
                  {c.name} ({c.provisions})
                </option>
              ))}
            </optgroup>
            <optgroup label="Every other origin">
              {countries.all.filter((c) => !c.named_by_chapter_99).map((c) => (
                <option key={c.country_code} value={c.country_code}>{c.name}</option>
              ))}
            </optgroup>
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-xs text-faint">Declared value (USD)</span>
          <input
            type="number" name="value" min="0" step="any" defaultValue={value}
            className="mt-1 w-40 border-b border-rule-strong bg-transparent py-1 font-mono
                       tabular text-ink outline-none focus:border-ink"
          />
        </label>
        {good.units.length > 0 && (
          <label className="text-sm">
            <span className="block text-xs text-faint">
              Quantity ({good.units.join(" / ")})
            </span>
            <input
              type="number" name="quantity" min="0" step="any" defaultValue={quantity}
              className="mt-1 w-40 border-b border-rule-strong bg-transparent py-1 font-mono
                         tabular text-ink outline-none focus:border-ink"
            />
          </label>
        )}
        <label className="text-sm">
          <span className="block text-xs text-faint">Entered on</span>
          <input
            type="date" name="on" defaultValue={on ?? asked.on_date}
            className="mt-1 border-b border-rule-strong bg-transparent py-1 font-mono
                       tabular text-ink outline-none focus:border-ink"
          />
        </label>
        <button
          type="submit"
          className="border border-rule-strong px-4 py-1.5 text-sm text-ink
                     hover:border-ink hover:bg-raised"
        >
          Recalculate
        </button>
      </form>

      {stack.layers.length > 0 && (
        <Section
          id="layers" title="Duties that change the rate"
          blurb="Each one names your code or your country, and says below how it got here."
        >
          {stack.layers.map((layer: Layer) => <LayerCard key={layer.hts} layer={layer} />)}
        </Section>
      )}

      {stack.reductions.length > 0 && (
        <Section
          id="reductions" title="Duty reductions that may apply"
          blurb={
            stack.reductions.length > 1
              ? "These are alternatives, not a stack. Which one is yours depends on what the "
                + "goods are — often a CAS registry number — and not on the HTS code."
              : "A subchapter II provision stands in for the base rate rather than adding to it."
          }
        >
          {stack.reductions.map((layer: Layer) => <LayerCard key={layer.hts} layer={layer} />)}
        </Section>
      )}

      {stack.origin_scoped.length > 0 && (
        <Section
          id="origin-scoped" title="Named your country, but described the goods in words"
          blurb="Left out of the figure above. Each names your country of origin and then
                 limits the goods it covers in prose that could not be turned into codes, so
                 it reaches every import from that origin. Read each one against your shipment."
        >
          {stack.origin_scoped.map((layer: Layer) => <LayerCard key={layer.hts} layer={layer} />)}
        </Section>
      )}

      {stack.origin_unresolved.length > 0 && (
        <Section
          id="origin-unresolved" title="Limited to a group of countries this data cannot list"
          blurb="Counted only towards the upper figure. Each limits itself to a set named in a
                 document none of the three sources contains — a General Note, a U.S. note's
                 exemption list, a CBP determination — so whether your origin is inside it is
                 not answerable here."
        >
          {stack.origin_unresolved.map((layer: Layer) => <LayerCard key={layer.hts} layer={layer} />)}
        </Section>
      )}

      {stack.competing_replacements.length > 0 && (
        <Section
          id="competing" title="More than one provision stands in lieu of the base rate"
          blurb="Counted only towards the upper figure. U.S. note 1 to subchapter III says a
                 Chapter 99 rate applies in lieu of the rate in chapters 1 to 98, so two of
                 them cannot both apply — and the schedule does not choose. These are usually
                 a quota's in-quota and over-quota rates, told apart by how much of the quota
                 has been filled this year."
        >
          {stack.competing_replacements.map((layer: Layer) => <LayerCard key={layer.hts} layer={layer} />)}
        </Section>
      )}

      {stack.not_eligible.length > 0 && (
        <Section
          id="not-eligible" title="Ruled out by their own wording"
          blurb="In neither figure, and this is a finding rather than a caveat: each states a
                 condition about the base rate of the goods it covers, and this good does not
                 meet it. The sentence that ruled it out is quoted on each."
        >
          {stack.not_eligible.map((layer: Layer) => (
            <LayerCard key={layer.hts} layer={layer} dimmed />
          ))}
        </Section>
      )}

      {stack.exclusions.length > 0 && (
        <Collapsed
          summary={`${stack.exclusions.reduce((n, g) => n + g.provisions.length, 0)} exclusions`}
          blurb="Each is a list of products carved out of a duty above. Whether your goods are
                 on one is a question about the goods, and the note is where it is answered."
        >
          <ul className="mt-4 space-y-2">
            {stack.exclusions.map((group) => (
              <li key={group.note_label ?? "none"} className="text-sm">
                {group.note_id ? (
                  <a
                    href={`/note/${group.note_id}`}
                    className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                  >
                    {group.note_label}
                  </a>
                ) : (
                  <span className="text-muted">cites no note</span>
                )}
                <span className="ml-2 font-mono text-xs text-faint">
                  {group.provisions.map((hts, index) => (
                    <span key={hts}>
                      {index > 0 && " · "}
                      <a href={`/rule/${hts}`} className="hover:text-ink hover:underline">
                        {hts}
                      </a>
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </Collapsed>
      )}

      {stack.inactive.length > 0 && (
        <Collapsed
          summary={`${stack.inactive.length} not in force on ${asked.on_date}`}
          blurb="Expired, not yet started, or stopped by a compiler's note. Kept because they
                 answer a different date, and because a schedule that hides them teaches the
                 wrong lesson about how often these change."
        >
          {stack.inactive.map((layer: Layer) => (
            <LayerCard key={layer.hts} layer={layer} dimmed />
          ))}
        </Collapsed>
      )}

      <Unknowns unknowns={stack.unknowns} />

      <footer className="mt-16 border-t border-rule pt-4 text-sm text-muted">
        Every number above came from{" "}
        <a
          href={jsonPath}
          className="font-mono underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
        >
          {jsonPath}
        </a>
        .
      </footer>
    </main>
  );
}
