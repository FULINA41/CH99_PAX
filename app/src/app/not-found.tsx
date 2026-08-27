export const metadata = { title: "Not found" };

// The default Next 404 is a bare line of text with no way back, which is what a reader got
// for mistyping a digit of a code -- the most likely way to arrive here.
export default function NotFound() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="font-serif text-3xl tracking-tight text-ink">No such page</h1>
      <p className="mt-4 max-w-prose leading-relaxed text-muted">
        Either the code does not exist in this revision of the schedule, or a digit is wrong.
        Chapter 99 provisions look like <span className="font-mono">9903.88.04</span>;
        classified goods look like <span className="font-mono">7208.51.00.30</span> and are
        eight or ten digits.
      </p>
      <p className="mt-6 flex flex-wrap gap-4 text-sm">
        <a
          href="/search"
          className="border border-field px-4 py-1.5 text-ink hover:border-ink hover:bg-raised"
        >
          Search for a code
        </a>
        <a
          href="/"
          className="border border-field px-4 py-1.5 text-ink hover:border-ink hover:bg-raised"
        >
          Start from the beginning
        </a>
      </p>
    </main>
  );
}
