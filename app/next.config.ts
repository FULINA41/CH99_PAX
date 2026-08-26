import type { NextConfig } from "next";

// The browser never talks to the API host directly. It asks this server for /api/..., which
// forwards to the FastAPI service -- so there is no CORS to configure, no API origin baked
// into a bundle, and the JSON a reader can inspect sits on the same origin as the page that
// rendered it. Server Components skip the hop and call API_URL themselves.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default config;
