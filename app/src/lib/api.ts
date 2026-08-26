// One place that knows where the API lives. Server Components reach it directly over the
// compose network; anything running in a browser goes through the rewrite in next.config.ts.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
