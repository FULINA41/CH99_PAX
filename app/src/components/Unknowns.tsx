import type { Unknown } from "@/lib/types";

// Not a disclaimer. For most of these the honest answer is a pointer, and a pointer with a
// search term is worth more than a hedge -- so every entry ends in something to do.
export function Unknowns({ unknowns }: { unknowns: Unknown[] }) {
  if (unknowns.length === 0) return null;

  return (
    <section id="unknowns" className="mt-14 scroll-mt-6">
      <h2 className="font-serif text-xl text-ink">What this cannot tell you</h2>
      <p className="mt-1 max-w-prose text-sm text-muted">
        {unknowns.length} question{unknowns.length === 1 ? "" : "s"} this data does not answer,
        and where each one is answered instead.
      </p>

      <ol className="mt-6 space-y-6">
        {unknowns.map((item, index) => (
          <li key={item.question} className="border-t border-rule pt-4">
            <div className="flex gap-3">
              <span className="font-mono text-sm text-faint tabular">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <h3 className="text-[0.95rem] font-medium text-ink">{item.question}</h3>
                <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-muted">
                  {item.why}
                </p>
                <p className="mt-2 text-sm">
                  <span className="text-faint">Where to settle it: </span>
                  <a
                    href={item.url}
                    className="underline decoration-rule-strong underline-offset-2 hover:decoration-ink"
                    rel="noreferrer noopener"
                    target="_blank"
                  >
                    {item.source_name}
                  </a>
                  <span className="text-faint"> — search for {item.what_to_search}</span>
                </p>
                {item.related_hts.length > 0 && (
                  <p className="mt-1.5 font-mono text-xs text-faint">
                    {item.related_hts.slice(0, 8).join(" · ")}
                    {item.related_hts.length > 8 && ` · +${item.related_hts.length - 8}`}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
