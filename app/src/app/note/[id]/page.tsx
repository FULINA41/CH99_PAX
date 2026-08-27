import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import type { NoteDetail } from "@/lib/types";

const PAGE = 200;

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    const { note } = await api<NoteDetail>(`/note/${id}?offset=0&limit=1`);
    return { title: note.label };
  } catch {
    return { title: "Note" };
  }
}

export default async function NotePage({
  params, searchParams,
}: { params: Promise<{ id: string }>; searchParams: Promise<{ from?: string }> }) {
  const { id } = await params;
  const { from } = await searchParams;
  const offset = Number(from ?? 0);

  let detail: NoteDetail;
  try {
    detail = await api<NoteDetail>(`/note/${id}?offset=${offset}&limit=${PAGE}`);
  } catch {
    notFound();
  }
  const { note } = detail;
  const shown = offset + detail.codes.length;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <a href="/" className="text-xs text-faint hover:text-muted">← Chapter 99</a>

      <header className="mt-6">
        <h1 className="font-serif text-3xl tracking-tight text-ink">{note.label}</h1>
        <p className="mt-2 text-sm text-muted">
          {note.content_kind === "subheading_list"
            ? "A list of subheadings."
            : note.content_kind === "mixed"
              ? "Prose with a list of subheadings inside it."
              : "Prose."}
          {note.listed_codes > 0 && (
            <> <span className="tabular text-ink">{note.listed_codes.toLocaleString()}</span>{" "}
              codes extracted.</>
          )}
          {note.page_from && (
            <span className="text-faint">
              {" "}· notes PDF, page {note.page_from}
              {note.page_to !== note.page_from && `–${note.page_to}`}
            </span>
          )}
        </p>
      </header>

      {detail.family.length > 1 && (
        <nav className="mt-6 flex flex-wrap gap-x-3 gap-y-1.5 border-t border-rule pt-4">
          {detail.family.map((sibling) => (
            <a
              key={sibling.id}
              href={`/note/${sibling.id}`}
              className={`text-sm ${
                sibling.id === note.id
                  ? "text-ink underline decoration-ink underline-offset-4"
                  : "text-muted hover:text-ink"
              }`}
            >
              {sibling.subdivision ? `(${sibling.subdivision})` : "whole note"}
              {sibling.listed_codes > 0 && (
                <span className="ml-1 text-xs text-faint">{sibling.listed_codes}</span>
              )}
            </a>
          ))}
        </nav>
      )}

      <section className="mt-8">
        <h2 className="text-xs font-medium uppercase tracking-wide text-faint">
          The note, as printed
        </h2>
        <div className="mt-3 max-h-[28rem] overflow-y-auto border-l-2 border-rule-strong pl-4">
          <p className="max-w-prose whitespace-pre-wrap text-[0.95rem] leading-relaxed text-ink">
            {note.body.length > 20000 ? `${note.body.slice(0, 20000)}\n\n…` : note.body}
          </p>
        </div>
      </section>

      {detail.codes.length > 0 && (
        <section className="mt-10">
          <h2 className="font-serif text-xl text-ink">Subheadings it lists</h2>
          <p className="mt-1 text-sm text-muted">
            In the order the note prints them. Showing{" "}
            <span className="tabular">{offset + 1}&ndash;{shown}</span> of{" "}
            <span className="tabular">{note.listed_codes.toLocaleString()}</span>.
          </p>
          <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-sm sm:grid-cols-4">
            {detail.codes.map((code) => (
              <li key={code.hts_prefix} className="text-muted tabular">
                {code.hts_prefix}
                {code.reaches === 0 && (
                  <span
                    className="ml-1 text-unsure"
                    title="Matches no row in this revision of the base schedule"
                  >
                    ·
                  </span>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex gap-4 text-sm">
            {offset > 0 && (
              <a
                href={`/note/${id}?from=${Math.max(0, offset - PAGE)}`}
                className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
              >
                ← previous {PAGE}
              </a>
            )}
            {shown < note.listed_codes && (
              <a
                href={`/note/${id}?from=${offset + PAGE}`}
                className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
              >
                next {Math.min(PAGE, note.listed_codes - shown)} →
              </a>
            )}
          </div>
        </section>
      )}

      <section className="mt-12">
        <h2 className="font-serif text-xl text-ink">
          Provisions that cite it
        </h2>
        <p className="mt-1 max-w-prose text-sm text-muted">
          {detail.citing.length === 0
            ? "None in this revision."
            : detail.citing.length === 1
              ? "One provision takes its scope, or part of it, from this note."
              : `${detail.citing.length} provisions take their scope, or part of it, from this note.`}
        </p>
        <ul className="mt-4">
          {detail.citing.map((cite) => (
            <li key={cite.rule_hts} className="border-t border-rule py-3">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <a
                  href={`/rule/${cite.rule_hts}`}
                  className="font-mono text-ink underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                >
                  {cite.rule_hts}
                </a>
                <span className="text-sm text-muted">{cite.rate_text || "—"}</span>
                {cite.programme && (
                  <span className="rounded-sm bg-raised px-2 py-0.5 text-xs text-muted">
                    {cite.programme}
                  </span>
                )}
                {cite.match_precision === "parent_fallback" && (
                  <span className="rounded-sm bg-unsure-soft px-2 py-0.5 text-xs text-unsure">
                    cites {cite.cited_subdivision}, matched to the whole note
                  </span>
                )}
              </div>
              <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted">
                {cite.description}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-16 border-t border-rule pt-4 text-sm text-muted">
        <a
          href={`/api/note/${id}`}
          className="font-mono underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
        >
          /api/note/{id}
        </a>
      </footer>
    </main>
  );
}
