import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests drive the real stack: Next.js production build -> FastAPI -> PostgreSQL.
 *
 * Each run resets a dedicated database (its name must end in _e2e; the reset script
 * refuses anything else), seeds demo data, and uses the offline AI fixture, so runs
 * are deterministic and never call OpenAI.
 *
 *   npm run test:e2e
 *
 * Needs PostgreSQL with a `sentinelai_e2e` database, and the backend installed
 * (pip install -e "backend[dev]"). Override E2E_DATABASE_URL if yours differs.
 */

const API_PORT = 8100;
const WEB_PORT = 3100;
const DATABASE_URL =
  process.env.E2E_DATABASE_URL ??
  "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelai_e2e";
// A fixed, test-only secret: the e2e stack runs locally and is torn down after.
const PROXY_SHARED_SECRET = "e2e-only-proxy-secret-0123456789abcdef";
const PYTHON = process.env.PYTHON ?? "python3";

export default defineConfig({
  testDir: "./e2e",
  // Tests share one seeded database, so run them one at a time in a fixed order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0, // a flaky test should fail loudly, not pass on a second try
  reporter: process.env.CI ? [["github"], ["line"], ["html", { open: "never" }]] : [["list"]],
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Lets a pre-installed Chromium be used instead of Playwright's download.
        launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
          ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
          : {},
      },
    },
  ],
  webServer: [
    {
      name: "api",
      cwd: "../backend",
      command: `${PYTHON} -m scripts.reset_db && ${PYTHON} -m uvicorn app.main:app --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      env: {
        DATABASE_URL,
        ENVIRONMENT: "development",
        JWT_SECRET: "e2e-only-jwt-secret-0123456789abcdefghij",
        PROXY_SHARED_SECRET,
        AI_OFFLINE_FIXTURES: "true",
        OPENAI_API_KEY: "",
      },
    },
    {
      name: "web",
      // Rewrites are resolved at build time, so build against the e2e API port.
      // E2E_NEXT_DEV=1 runs the dev server instead, for readable React error messages.
      command: process.env.E2E_NEXT_DEV
        ? `npx next dev -p ${WEB_PORT}`
        : `npx next build && npx next start -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/login`,
      reuseExistingServer: false,
      timeout: 300_000,
      stdout: "ignore",
      env: {
        BACKEND_URL: `http://localhost:${API_PORT}`,
        PROXY_SHARED_SECRET,
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
