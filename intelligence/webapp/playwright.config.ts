import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const webappRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(webappRoot, "../..");
const serverPort = process.env.WORKBENCH_E2E_PORT ?? "8791";
const serverURL = `http://127.0.0.1:${serverPort}`;
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
const fixtureRoot = resolve(
  repoRoot,
  "intelligence/tests/fixtures/chat_workbench_repo",
);
const usersRoot = resolve(webappRoot, "test-results/workbench-users");
const emptyLlmKeys = [
  "FORESIGHT_BUILTIN_LLM_API_KEY",
  "DEEPSEEK_API_KEY",
  "MOONSHOT_API_KEY",
  "KIMI_API_KEY",
  "DASHSCOPE_API_KEY",
  "QWEN_API_KEY",
  "ZHIPU_API_KEY",
  "GLM_API_KEY",
  "OPENAI_API_KEY",
  "LLM_API_KEY",
  "FORESIGHT_BUILTIN_LLM_API_KEY",
]
  .map((name) => `${name}=`)
  .join(" ");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: serverURL,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `rm -rf ${shellQuote(usersRoot)} && mkdir -p ${shellQuote(usersRoot)} && cd ${shellQuote(repoRoot)} && WORKBENCH_REPO_ROOT=${shellQuote(fixtureRoot)} WORKBENCH_TEST_RUN_DELAY_MS=500 FINANCE_WS=${shellQuote(fixtureRoot)} KB_VAULT=${shellQuote(resolve(fixtureRoot, "wiki"))} FORESIGHT_USER=default FORESIGHT_USERS_DIR=${shellQuote(usersRoot)} ${emptyLlmKeys} ${shellQuote(python)} -m uvicorn intelligence.api.app:app --host 127.0.0.1 --port ${shellQuote(serverPort)}`,
    url: serverURL,
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
