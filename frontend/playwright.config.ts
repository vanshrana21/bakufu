import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e", fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3100", viewport: { width: 1920, height: 1080 }, trace: "retain-on-failure",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
  // These specs assert exact fixture values - 32% shortfall, five register rows,
  // the "synthetic" labels - so they must run in fixture mode. Left to inherit,
  // a developer with NEXT_PUBLIC_API_BASE_URL in .env.local ran them against the
  // live backend, where the numbers move monthly and every assertion failed for
  // the wrong reason. Blank here wins: a real environment variable takes
  // precedence over .env.local, and "" counts as set.
  // The live path is verified separately, against the running API.
  webServer: { command: "npx next dev -p 3100 --hostname 127.0.0.1", url: "http://127.0.0.1:3100/explorer", reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_API_BASE_URL: "", BAKUFU_API_KEY: "", NEXT_PUBLIC_MAPBOX_TOKEN: "", NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN: "", NEXT_TELEMETRY_DISABLED: "1" } },
});
