import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";


const currentDirectory = fileURLToPath(new URL(".", import.meta.url));


export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 60_000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: ".venv/bin/uvicorn resume_mvp.main:app --host 127.0.0.1 --port 8000",
      cwd: resolve(currentDirectory, "../backend"),
      env: {
        RESUME_MVP_TEST_PROVIDER: "1",
        RESUME_DATA_DIR: resolve(currentDirectory, "../.data/e2e"),
      },
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "pnpm exec vite --host 127.0.0.1 --port 5173",
      cwd: currentDirectory,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
