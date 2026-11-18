import { defineConfig } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

// The test account lives in the repo's .env (TEST_USER_EMAIL / TEST_USER_PASSWORD).
// Read it without printing anything; tests that need it skip when it's missing.
try {
  const env = readFileSync(path.join(__dirname, "..", ".env"), "utf-8");
  for (const line of env.split(/\r?\n/)) {
    const m = /^(TEST_USER_EMAIL|TEST_USER_PASSWORD)=(.*)$/.exec(line.trim());
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
  }
} catch {
  /* no .env: logged-in tests skip */
}

/**
 * Smoke tests at phone (375 px) and desktop (1280 px) widths.
 * Needs the API on :8000 (fixtures mode) and the app on :3000:
 *   backend:  uvicorn api.main:app --port 8000
 *   frontend: npm run build && npm run start
 *   then:     npx playwright test
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "phone-375", use: { browserName: "chromium", viewport: { width: 375, height: 812 }, hasTouch: true } },
    { name: "desktop-1280", use: { browserName: "chromium", viewport: { width: 1280, height: 800 } } },
  ],
});
