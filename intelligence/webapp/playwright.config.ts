import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const webappRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(webappRoot, "../..");
const pythonCandidates = [
  process.env.WORKBENCH_PYTHON,
  resolve(repoRoot, ".venv-workbench/bin/python"),
  resolve(repoRoot, ".venv/bin/python"),
  "python3",
].filter((candidate): candidate is string => Boolean(candidate));
const python =
  pythonCandidates.find(
    (candidate) => !candidate.includes("/") || existsSync(candidate),
  ) ?? "python3";
const shellQuote = (value: string) => `'${value.replaceAll("'", "'\"'\"'")}'`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8791",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `cd ${shellQuote(repoRoot)} && ${shellQuote(python)} -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port 8791`,
    url: "http://127.0.0.1:8791",
    reuseExistingServer: false,
    timeout: 120000,
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 768 } } },
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
