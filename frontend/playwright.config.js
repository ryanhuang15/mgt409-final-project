import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  workers: 1,
  fullyParallel: false,
  outputDir: "../runtime/playwright-results",
  reporter: [
    ["list"],
    ["json", { outputFile: "../runtime/playwright-results.json" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:8000",
    viewport: { width: 1440, height: 1050 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  expect: { timeout: 10000 },
});
