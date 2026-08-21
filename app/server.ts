// Bare scaffold. It connects to Postgres and serves one page.
// Everything past that is yours — routes, framework, rendering, all of it.
//
// Nothing here is load-bearing. Delete it, or don't use it at all.

import { SQL } from "bun";

const PORT = Number(process.env.PORT ?? 3000);
const DATABASE_URL =
  process.env.DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/chp99";

const sql = new SQL(DATABASE_URL);

/** Whatever you've created in the chp99 database so far. */
async function tables(): Promise<string[]> {
  const rows = await sql`
    SELECT tablename AS name FROM pg_tables WHERE schemaname = 'public'
    UNION ALL
    SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'
    UNION ALL
    SELECT viewname FROM pg_views WHERE schemaname = 'public'
    ORDER BY name
  `;
  return rows.map((r: { name: string }) => r.name);
}

function page(body: string): Response {
  return new Response(
    `<!doctype html>
<meta charset="utf-8">
<title>chp99</title>
<style>
  body { font: 15px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
         margin: 4rem auto; max-width: 44rem; padding: 0 1.5rem; }
  code { background: #f4f4f5; padding: 0.1em 0.35em; border-radius: 3px; }
  .err { color: #b91c1c; }
</style>
${body}`,
    { headers: { "content-type": "text/html; charset=utf-8" } },
  );
}

const server = Bun.serve({
  port: PORT,
  routes: {
    "/": async () => {
      try {
        const found = await tables();
        return page(
          `<h1>chp99</h1>
           <p>Database connection is up.</p>
           ${
             found.length
               ? `<p>Relations in <code>public</code>:</p><ul>${found
                   .map((t) => `<li><code>${t}</code></li>`)
                   .join("")}</ul>`
               : `<p>No relations yet — run your migrations.</p>`
           }
           <p>Edit <code>app/server.ts</code> to start building.</p>`,
        );
      } catch (err) {
        return page(
          `<h1>chp99</h1>
           <p class="err">Could not reach Postgres at <code>${DATABASE_URL}</code></p>
           <pre class="err">${err instanceof Error ? err.message : String(err)}</pre>
           <p>Is <code>docker compose up -d</code> running?</p>`,
        );
      }
    },
  },
});

console.log(`→ http://localhost:${server.port}`);
