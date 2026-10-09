import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const fixture = resolve(root, "intelligence/tests/fixtures/chat_workbench_repo");
const isolated = resolve(root, "intelligence/webapp/test-results/board-calendar");
const port = process.env.BOARD_CALENDAR_E2E_PORT ?? "8795";
const python = process.env.WORKBENCH_PYTHON ?? resolve(root, ".venv-workbench/bin/python");
const quote = (s: string) => `'${s.replaceAll("'", "'\"'\"'")}'`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "board-calendar.spec.ts",
  outputDir: "./test-results/board-calendar-browser",
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    launchOptions: process.env.WORKBENCH_CHROMIUM_EXECUTABLE ? {
      executablePath: process.env.WORKBENCH_CHROMIUM_EXECUTABLE,
      args: ["--no-sandbox", "--disable-dev-shm-usage", "--no-zygote"],
    } : {},
  },
  webServer: {
    command: `${quote(python)} e2e/prepare_board_calendar_fixture.py && cd ${quote(root)} && ${quote(python)} -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port ${port}`,
    env: {
      WORKBENCH_REPO_ROOT: fixture, FINANCE_WS: fixture, KB_VAULT: resolve(fixture, "wiki"),
      MARKET_FEATURE_STORE_DB: resolve(isolated, "market.duckdb"),
      FORESIGHT_USERS_DIR: resolve(isolated, "users"), FORESIGHT_USER: "default",
      FORESIGHT_EPISODE_STORE: resolve(isolated, "episodes"),
      OPENAI_API_KEY: "", LLM_API_KEY: "", FORESIGHT_BUILTIN_LLM_API_KEY: "",
      DEEPSEEK_API_KEY: "", MOONSHOT_API_KEY: "", KIMI_API_KEY: "",
      DASHSCOPE_API_KEY: "", QWEN_API_KEY: "", ZHIPU_API_KEY: "", GLM_API_KEY: "",
    },
    url: `http://127.0.0.1:${port}`, reuseExistingServer: false, timeout: 120000,
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "tablet", use: { viewport: { width: 1024, height: 768 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
});
