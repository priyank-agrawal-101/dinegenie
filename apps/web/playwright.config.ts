import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const localPython = resolve(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
const python = process.env.PYTHON ?? (existsSync(localPython) ? localPython : "python");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 2,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    { name: "tablet", use: { browserName: "chromium", viewport: { width: 768, height: 1024 } } },
  ],
  webServer: [{
    command: `"${python}" -m pipelines.cli --mode fixture --runtime-root runtime-data/phase4-e2e && "${python}" -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8014`,
    cwd: root,
    env: { APP_DATABASE_URL: "sqlite:///./runtime-data/phase4-e2e/restaurants.db", APP_LLM_ENABLED: "false", APP_ENVIRONMENT: "test" },
    url: "http://127.0.0.1:8014/health/ready",
    reuseExistingServer: false,
    timeout: 60_000,
  }, {
    command: "npm run build && npm run preview -- --host 127.0.0.1",
    url: "http://127.0.0.1:4173",
    env: { API_PROXY_TARGET: "http://127.0.0.1:8014", VITE_API_BASE_URL: "" },
    reuseExistingServer: false,
    timeout: 120_000,
  }],
});
