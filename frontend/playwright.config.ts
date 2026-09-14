import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e", fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3100", viewport: { width: 1920, height: 1080 }, trace: "retain-on-failure",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
  webServer: { command: "npx next dev -p 3100 --hostname 127.0.0.1", url: "http://127.0.0.1:3100/explorer", reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_MAPBOX_TOKEN: "", NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN: "", NEXT_TELEMETRY_DISABLED: "1" } },
});
