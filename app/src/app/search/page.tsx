import { api } from "@/lib/api";
import type { Countries } from "@/lib/types";

type Result = {
  hts: string;
  full_description: string;
  units: string[] | null;
  rate_text: string | null;
  rate_kind: string;
  rate_ad_valorem_pct: string | null;
  programmes: string[] | null;
};

type Results = { query: string; matched_by: "words" | "code" | "spelling"; results: Result[] };

const MATCHED: Record<Results["matched_by"], string> = {
  words: "matched on the schedule's own wording",
  code: "matched as a code",
  spelling: "no wording matched, so these are the closest spellings",
};

export default async function SearchPage(
  { searchParams }: { searchParams: Promise<{ q?: string; country?: string }> },
) {
  const { q, country } = await searchParams;
  const countries = await api<Countries>("/countries");
  // The origin goes to the API, not just into the links: without it the results would name
  // trade actions that cannot reach these goods from this country, and the duty page one
  // click later would show none of them.
  const found = q
    ? await api<Results>(
        `/search?q=${encodeURIComponent(q)}${country ? `&country=${country}` : ""}`,
      )
    : null;

  const to = (hts: string) =>
    country ? `/duty/${hts}?country=${country}` : `/duty/${hts}`;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <a href="/" className="font-mono text-xs text-faint hover:text-muted">← Chapter 99</a>

      <h1 className="mt-6 font-serif text-3xl tracking-tight text-ink">Find a code</h1>

      <form action="" className="mt-6 flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="block text-xs text-faint">Words, or a code</span>
          <input
            type="search" name="q" required defaultValue={q} placeholder="hot-rolled steel plate"
            className="mt-1 w-80 border-b border-rule-strong bg-transparent py-1 text-ink
                       outline-none placeholder:text-faint focus:border-ink"
          />
        </label>
        <label className="text-sm">
          <span className="block text-xs text-faint">Country of origin</span>
          <select
            name="country" defaultValue={country ?? ""}
            className="mt-1 w-52 border-b border-rule-strong bg-transparent py-1 text-ink
                       outline-none focus:border-ink"
          >
            <option value="">— choose later —</option>
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
        <button
          type="submit"
          className="border border-rule-strong px-4 py-1.5 text-sm text-ink
                     hover:border-ink hover:bg-raised"
        >
          Search
        </button>
      </form>

      <p className="mt-4 max-w-prose text-sm leading-relaxed text-muted">
        This searches the schedule&rsquo;s prose, which is not how anyone describes a product —
        a laptop bag is filed as <em>&ldquo;Trunks, suitcases &hellip; with outer surface of
        textile materials&rdquo;</em>. Deciding which line a good belongs to is classification,
        it is the importer&rsquo;s legal responsibility, and this site does not do it. Use{" "}
        <a
          href="https://rulings.cbp.gov/"
          target="_blank" rel="noreferrer noopener"
          className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
        >
          CBP CROSS rulings
        </a>{" "}
        to see how a real product was actually classified.
      </p>

      {found && (
        <section className="mt-10">
          <h2 className="text-xs font-medium uppercase tracking-wide text-faint">
            {found.results.length} result{found.results.length === 1 ? "" : "s"} ·{" "}
            {MATCHED[found.matched_by]}
          </h2>

          {found.results.some((row) => row.programmes?.length) && (
            <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">
              A tag names a trade action with a Chapter 99 provision that mentions the code
              {country ? " and reaches goods from this origin" : ""} — not a duty you will
              pay. Whether one covers your goods is what the code&rsquo;s own page works out.
              The names are this site&rsquo;s attribution; the schedule never states one.
              <span className="text-faint"> · not in the schedule</span>
            </p>
          )}

          <ul className="mt-4">
            {found.results.map((row) => (
              <li key={row.hts} className="border-t border-rule py-4">
                <a href={to(row.hts)} className="group flex flex-wrap items-baseline gap-x-4">
                  <span className="font-mono text-ink group-hover:underline">{row.hts}</span>
                  <span className="font-mono text-sm tabular text-muted">
                    {row.rate_text || "—"}
                  </span>
                  {row.programmes?.map((programme) => (
                    <span
                      key={programme}
                      className="rounded-sm bg-raise-soft px-2 py-0.5 text-xs text-raise"
                      title="Named by this site, not by the schedule — see the code's own page"
                    >
                      {programme}
                    </span>
                  ))}
                </a>
                <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-muted">
                  {row.full_description}
                </p>
              </li>
            ))}
          </ul>

          {found.results.length === 0 && (
            <p className="mt-4 max-w-prose text-sm text-muted">
              Nothing matched. The schedule&rsquo;s wording is often a century old — try the
              material rather than the product, or a broader word.
            </p>
          )}
        </section>
      )}
    </main>
  );
}
