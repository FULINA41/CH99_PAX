import { api } from "@/lib/api";

type Meta = {
  release: { release_name: string; release_title: string; fetched_at: string; sources: number } | null;
  counts: Record<string, number>;
  parse_issues: { stage: string; issue_kind: string; count: number }[];
};

export default async function Home() {
  const meta = await api<Meta>("/meta");

  return (
    <main>
      <h1>Chapter 99</h1>
      <p>
        Data from <strong>{meta.release?.release_title ?? "an unknown revision"}</strong> (
        <code>{meta.release?.release_name}</code>), parsed from {meta.release?.sources} sources.
      </p>

      <h2>Rows</h2>
      <table>
        <tbody>
          {Object.entries(meta.counts).map(([relation, count]) => (
            <tr key={relation}>
              <td><code>{relation}</code></td>
              <td className="num">{count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>What the parser could not read</h2>
      <table>
        <thead>
          <tr><th>stage</th><th>issue</th><th className="num">count</th></tr>
        </thead>
        <tbody>
          {meta.parse_issues.map((issue) => (
            <tr key={`${issue.stage}/${issue.issue_kind}`}>
              <td>{issue.stage}</td>
              <td><code>{issue.issue_kind}</code></td>
              <td className="num">{issue.count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
