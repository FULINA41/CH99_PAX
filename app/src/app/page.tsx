import { api } from "@/lib/api";

type Meta = {
  release: { release_name: string; release_title: string } | null;
  counts: Record<string, number>;
};

const CHANGES = [
  "add an extra duty to the base rate;",
  "replace the base rate;",
  "reduce or remove a duty; or",
  "leave the base rate unchanged while imposing other conditions.",
];

const WORKFLOW = [
  "Describe the product",
  "identify its HTS number",
  "find the base rate",
  "check the country, date and other conditions",
  "identify applicable Chapter 99 provisions",
  "apply each provision as instructed",
  "calculate the final duty",
];

// Three worked examples, each demonstrating a different thing Chapter 99 does. They are the
// way in: a novice opening a tariff site does not know a code to type, and "search for your
// product" is a worse first instruction than "look at what happens to steel".
const EXAMPLES = [
  {
    hts: "7208.51.00.30",
    country: "CN",
    value: "100000",
    good: "Hot-rolled steel plate",
    origin: "China",
    teaches:
      "Two duties reach the same shipment by different routes — one through a list inside a "
      + "note in a PDF, one on country of origin alone — and only one of them can be shown "
      + "to cover this code. The answer is a range, and the reason is on the page.",
  },
  {
    hts: "2922.49.30.00",
    country: "DE",
    value: "50000",
    good: "An amino-acid compound",
    origin: "Germany",
    teaches:
      "Four duty reductions cite this one code, each naming a different substance by CAS "
      + "number. They are alternatives, not a stack, and nothing in the tariff code chooses "
      + "between them — the goods do.",
  },
  {
    hts: "7208.51.00.30",
    country: "DE",
    value: "100000",
    good: "The same steel plate",
    origin: "Germany",
    teaches:
      "The control. Same code, different origin, nothing from Chapter 99 applies, and the "
      + "duty is the base rate the schedule prints. Most goods look like this.",
  },
];

export default async function Home() {
  const meta = await api<Meta>("/meta");

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="font-serif text-4xl tracking-tight text-ink">Chapter 99</h1>

      <h2 className="mt-6 max-w-prose font-serif text-2xl leading-snug text-ink">
        How is the duty on an imported product determined?
      </h2>
      <p className="mt-5 max-w-prose leading-relaxed text-muted">
        A product name alone is not enough to determine its duty rate. First, the product must
        be classified under Chapters 1&ndash;97 of the U.S. tariff schedule and assigned an HTS
        number. That classification provides the ordinary, or base, duty rate.
      </p>
      <p className="mt-4 max-w-prose leading-relaxed text-muted">
        The result can also depend on the product&rsquo;s material, use and specifications, as
        well as its country of origin, date of import, declared value and quantity.
      </p>
      <p className="mt-4 max-w-prose leading-relaxed text-muted">
        Chapter 99 comes next. It does not classify the product or replace its ordinary HTS
        number. Instead, it contains temporary or special provisions that may change what an
        already-classified product pays. Depending on the provision, a Chapter 99 rate may:
      </p>
      <ul className="mt-3 max-w-prose space-y-1.5 leading-relaxed text-muted">
        {CHANGES.map((change) => (
          <li key={change} className="flex gap-2.5">
            <span aria-hidden className="text-faint">&middot;</span>
            <span>{change}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 max-w-prose leading-relaxed text-muted">
        Finding the right provision is not always straightforward. A Chapter 99 heading may
        refer to ordinary HTS numbers in prose, apply only to products from certain countries,
        or rely on lists and conditions found in the accompanying U.S. notes.
      </p>

      <h3 className="mt-8 text-xs font-medium uppercase tracking-wide text-faint">
        The workflow
      </h3>
      <ol className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-2 text-sm">
        {WORKFLOW.map((step, index) => (
          <li key={step} className="flex items-center gap-2">
            {index > 0 && <span aria-hidden className="text-faint">&rarr;</span>}
            <span className="border border-rule px-2 py-1 text-muted">{step}</span>
          </li>
        ))}
      </ol>

      <p className="mt-6 max-w-prose leading-relaxed text-ink">
        This site works through that process and shows how each part of the result was reached.
        It also identifies questions the tariff data alone cannot answer, such as whether a
        shipment qualifies for a particular exclusion or tariff-rate quota.
      </p>

      <section className="mt-14">
        <h2 className="font-serif text-xl text-ink">Start with a worked example</h2>
        <ul className="mt-6 space-y-8">
          {EXAMPLES.map((example) => (
            <li key={`${example.hts}-${example.country}`} className="border-t border-rule pt-5">
              <a
                className="group flex flex-wrap items-baseline gap-x-3"
                href={`/duty/${example.hts}?country=${example.country}&value=${example.value}`}
              >
                <span className="font-mono text-lg text-ink group-hover:underline">
                  {example.hts}
                </span>
                <span className="text-sm text-muted">
                  {example.good} · product of {example.origin}
                </span>
              </a>
              <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted">
                {example.teaches}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-14 border-t border-rule pt-6">
        <h2 className="font-serif text-xl text-ink">Or look one up</h2>
        <form action="/search" className="mt-4 flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <span className="block text-xs text-faint">Search the schedule</span>
            <input
              type="search" name="q" required placeholder="steel plate, hot-rolled"
              className="mt-1 w-72 border-b border-field bg-transparent py-1 text-ink
                         outline-none placeholder:text-faint focus:border-ink"
            />
          </label>
          <button
            type="submit"
            className="border border-field px-4 py-1.5 text-sm text-ink
                       hover:border-ink hover:bg-raised"
          >
            Search
          </button>
        </form>
        <p className="mt-3 max-w-prose text-sm text-muted">
          Matches the schedule&rsquo;s own wording, which is not the wording anyone uses for a
          product. Classification is the importer&rsquo;s responsibility and this site does not
          do it.
        </p>
      </section>

      <footer className="mt-16 border-t border-rule pt-4 text-sm text-muted">
        {meta.release?.release_title} ({meta.release?.release_name}) ·{" "}
        <span className="tabular">{meta.counts.hts_base?.toLocaleString()}</span> classified
        codes · <span className="tabular">{meta.counts.rule?.toLocaleString()}</span> Chapter
        99 provisions · <span className="tabular">{meta.counts.note?.toLocaleString()}</span>{" "}
        notes ·{" "}
        <a href="/api/meta" className="font-mono underline decoration-rule-strong underline-offset-2 hover:decoration-ink">
          /api/meta
        </a>
      </footer>
    </main>
  );
}
