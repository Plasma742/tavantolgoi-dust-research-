import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend, so the browser never needs
// cross-origin access and never sees Earth Engine credentials or URLs.
export default defineConfig({
  plugins: [react()],
  // MapLibre GL alone is ~1 MB minified; the warning is expected for this single-page research app.
  build: { chunkSizeWarningLimit: 1600 },
  // MapLibre GL v6 runs its worker as an ES module; bundle it as one ES worker file.
  worker: { format: "es" },
  server: {
    host: "127.0.0.1",
    port: 5173,
    // GitHub Codespaces serves the dev server through *.app.github.dev (private port forwarding).
    allowedHosts: process.env.CODESPACES === "true" ? [".app.github.dev"] : undefined,
    proxy: {
      "/api": { target: process.env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
