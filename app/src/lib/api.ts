// One place that knows where the API lives. Server Components reach it directly over the
// compose network; anything running in a browser goes through the rewrite in next.config.ts.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function api<T>(path: string): Promise<T> {
  // no-store rather than a revalidate window: the data changes only when the parser runs,
  // and when it does, a page showing the previous revision's duty is wrong rather than
  // stale. Correctness is the whole point of this app; the queries behind it are measured
  // in single-digit milliseconds, so there is nothing to buy by caching.
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
