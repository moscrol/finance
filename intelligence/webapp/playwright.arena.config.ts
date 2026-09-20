import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const python = process.env.WORKBENCH_PYTHON ?? resolve(root, ".venv-workbench/bin/python");
const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
export default defineConfig({
  testDir: "./arena_e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:8826", trace: "retain-on-failure" },
  webServer: {
    command: `${quote(python)} -m intelligence.webapp.arena_e2e.serve`,
    cwd: root,
    url: "http://127.0.0.1:8826/api/arena/bootstrap",
    reuseExistingServer: false,
    timeout: 30000,
  },
  projects: [
    { name: "arena-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "arena-mobile", use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
