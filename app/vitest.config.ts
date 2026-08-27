import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// The components under test are server components only in the sense that Next renders them on
// the server: they take props and return JSX, with no async or request-scoped API, so they
// render under jsdom exactly as they do in the app.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.tsx"],
  },
});
