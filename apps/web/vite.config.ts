import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const apiTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";
const proxy = { "/api": apiTarget, "/health": apiTarget };

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy,
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
