import { defineConfig, devices } from "@playwright/test";

const apiEnv = {
  ...process.env,
  DATABASE_URL: "sqlite:///./data/e2e.db",
  DEMO_MODE: "true",
  PRICES_ONLINE: "false",
};

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --port 8000",
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      env: apiEnv,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
    },
  ],
});
