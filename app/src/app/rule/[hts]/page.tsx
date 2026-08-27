import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import { clip } from "@/lib/types";
import type { RuleDetail } from "@/lib/types";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 border-t border-rule py-2.5 text-sm">
      <dt className="w-44 shrink-0 text-faint">{label}</dt>
      <dd className="min-w-0 text-muted">{children}</dd>
    </div>
  );
}

export async function generateMetadata({ params }: { params: Promise<{ hts: string }> }) {
  const { hts } = await params;
  return { title: `${hts} · provision` };
}

export default async function RulePage({ params }: { params: Promise<{ hts: string }> }) {
  const { hts } = await params;
  let detail: RuleDetail;
  try {
    detail = await api<RuleDetail>(`/rule/${hts}`);
  } catch {
    notFound();
  }
  const { rule } = detail;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <a href="/" className="text-xs text-faint hover:text-muted">← Chapter 99</a>

      <header className="mt-6">
        <p className="text-xs uppercase tracking-wide text-faint">Chapter 99 provision</p>
        <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-2">
          <h1 className="font-mono text-3xl font-medium tracking-tight text-ink">{rule.hts}</h1>
          {rule.label && (
            <span className="rounded-sm bg-raised px-2 py-1 text-xs text-muted">
              {rule.label}<span className="ml-1.5 text-faint">· not in the schedule</span>
            </span>
          )}
          {rule.status !== "in_force" && (
            <span className="rounded-sm bg-unsure-soft px-2 py-1 text-xs text-unsure">
              {rule.status_reading}
            </span>
          )}
        </div>
        <p className="mt-4 max-w-prose leading-relaxed text-ink">{rule.full_description}</p>
      </header>

      <section className="mt-10">
        <h2 className="font-serif text-xl text-ink">What it does</h2>
        <dl className="mt-3">
          <Row label="Rate, as printed">
            <span className="text-ink">{rule.rate_text || "— none printed —"}</span>
          </Row>
          <Row label="Read as">
            <span className="text-ink">{rule.rate_kind_reading}</span>
            {rule.rate_ad_valorem_pct !== null && (
              <span className="tabular"> · {Number(rule.rate_ad_valorem_pct)}%</span>
            )}
            {rule.rate_specific_amount !== null && (
              <span className="tabular">
                {" "}· ${Number(rule.rate_specific_amount)} per {rule.rate_specific_unit}
              </span>
            )}
          </Row>
          {rule.additional_duty_text && (
            <Row label="Additional duty">{rule.additional_duty_text}</Row>
          )}
          <Row label="What it covers">
            <span className="text-ink">{rule.scope_reading}</span>
            {rule.scope === "by_country_all_goods" && (
              <div className="mt-1 text-xs text-unsure">
                Because the goods are described in words rather than by code, this site has to
                read it as reaching every import from that origin.
              </div>
            )}
          </Row>
          {(rule.effective_from || rule.effective_to) && (
            <Row label="In force">
              <span className="tabular">
                {rule.effective_from ?? "— unstated —"} to {rule.effective_to ?? "— open —"}
              </span>
            </Row>
          )}
          {rule.status_note && (
            <Row label="Compiler's note"><em>{rule.status_note}</em></Row>
          )}
          {rule.statute && (
            <Row label="Authority">
              {rule.statute} · {rule.agency}
              <div className="mt-1 text-xs text-faint">
                Added by this site, not printed in the schedule, which almost never names the
                law behind a provision. It is shown because the provisions in this heading
                family state the subject matter themselves: {rule.evidence}.{" "}
                <a
                  href={rule.reference_url ?? "#"} target="_blank" rel="noreferrer noopener"
                  className="underline decoration-rule-strong underline-offset-2"
                >
                  Check it in the Federal Register
                </a>
              </div>
            </Row>
          )}
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="font-serif text-xl text-ink">What it reaches</h2>
        <p className="mt-1 max-w-prose text-sm text-muted">
          {rule.base_codes === null
            ? "Its text names no code in chapters 1\u201397, and neither does any note it cites."
            : <>
                <span className="tabular text-ink">{rule.base_codes.toLocaleString()}</span>{" "}
                codes in chapters 1&ndash;97 —{" "}
                <span className="tabular">{rule.direct_codes?.toLocaleString()}</span> named in
                its own text and{" "}
                <span className="tabular">{rule.note_codes?.toLocaleString()}</span> through a
                note it cites.
              </>}
        </p>

        {detail.cited_codes.length > 0 && (
          <p className="mt-3 text-sm text-muted">
            Names in chapters 1&ndash;97:{" "}
            <span className="font-mono">
              {detail.cited_codes.map((c) => c.cited_code).join(" · ")}
            </span>
          </p>
        )}

        {detail.notes.length > 0 && (
          <ul className="mt-4 space-y-2">
            {detail.notes.map((note) => (
              <li key={note.cited_text} className="border-t border-rule pt-2 text-sm">
                {note.note_id ? (
                  <a
                    href={`/note/${note.note_id}`}
                    className="text-ink underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                  >
                    {note.label}
                  </a>
                ) : (
                  <span className="text-muted">{note.cited_text}</span>
                )}
                <span className="ml-2 text-faint">
                  {note.listed_codes > 0
                    ? `lists ${note.listed_codes.toLocaleString()} code${
                        note.listed_codes === 1 ? "" : "s"}`
                    : "prose, no code list"}
                  {note.page_from && ` · PDF page ${note.page_from}`}
                </span>
                <div className="mt-1 text-xs">
                  <span className="text-faint">cited as</span>{" "}
                  <span className="text-muted">“{note.cited_text}”</span>
                  {note.match_precision === "parent_fallback" && (
                    <span className="ml-2 text-unsure">
                      — it names subdivision {note.cited_subdivision}, which could not be
                      read apart from the rest of the note, so what is shown is the whole note
                      and is wider than this provision
                    </span>
                  )}
                  {note.match_precision === "chapter_note" && (
                    <span className="ml-2 text-faint">
                      — a chapter note, which lives in another chapter&rsquo;s document and is
                      not in this PDF
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}

        {detail.sample.length > 0 && (
          <details className="mt-4">
            <summary className="text-sm text-muted">
              A sample of the codes it reaches
            </summary>
            <table className="ml-4 mt-3 w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-faint">
                  <th className="pb-1 font-medium">base code</th>
                  <th className="pb-1 font-medium">reached via</th>
                  <th className="pb-1 font-medium">how</th>
                </tr>
              </thead>
              <tbody>
                {detail.sample.map((row) => (
                  <tr key={`${row.base_hts}-${row.cited_code}`} className="border-t border-rule">
                    <td className="py-1 font-mono text-muted">{row.base_hts}</td>
                    <td className="py-1 font-mono text-faint">{row.cited_code}</td>
                    <td className="py-1 text-faint">{row.path} · {row.how}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </section>

      {(detail.countries.length > 0 || detail.identifiers.length > 0) && (
        <section className="mt-10">
          <h2 className="font-serif text-xl text-ink">What goods, and from where</h2>
          <dl className="mt-3">
            {detail.countries.length > 0 && (
              <Row label="Countries named">
                {detail.countries.map((c) => c.country_name).join(", ")}
              </Row>
            )}
            {detail.identifiers.length > 0 && (
              <Row label="CAS numbers">
                <span className="font-mono">
                  {detail.identifiers.map((i) => i.value).join(", ")}
                </span>
                <div className="mt-1 text-xs text-faint">
                  The HTS code does not choose between provisions citing the same subheading —
                  the substance does, and a CAS number names it exactly.
                </div>
              </Row>
            )}
          </dl>
        </section>
      )}

      {(detail.carves_out.length > 0 || detail.carved_out_by.length > 0) && (
        <section className="mt-10">
          <h2 className="font-serif text-xl text-ink">Exclusions</h2>
          <p className="mt-1 max-w-prose text-sm text-muted">
            Exclusions run in both directions and mean opposite things, so they are listed
            apart. Whether your goods are described by any of them is a question about the
            goods.
          </p>
          {[
            { title: "This provision carves out", edges: detail.carves_out, key: "target_hts" as const },
            { title: "This provision is carved out by", edges: detail.carved_out_by, key: "source_hts" as const },
          ].filter((g) => g.edges.length > 0).map((group) => (
            <div key={group.title} className="mt-4">
              <h3 className="text-xs font-medium uppercase tracking-wide text-faint">
                {group.title}
              </h3>
              <ul className="mt-2 space-y-1">
                {group.edges.map((edge) => (
                  <li key={`${edge.source_hts}-${edge.target_hts}`} className="text-sm">
                    <a
                      href={`/rule/${edge[group.key]}`}
                      className="font-mono text-ink underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                    >
                      {edge[group.key]}
                    </a>
                    <span className="ml-2 text-muted">
                      {clip(edge.description ?? "", 110)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      <footer className="mt-16 border-t border-rule pt-4 text-sm text-muted">
        <a
          href={`/api/rule/${hts}`}
          className="font-mono underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
        >
          /api/rule/{hts}
        </a>
      </footer>
    </main>
  );
}
