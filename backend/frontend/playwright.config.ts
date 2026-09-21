import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e", fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3000", viewport: { width: 1920, height: 1080 }, trace: "retain-on-failure",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
    // Port 3000, not 3100: the backend's CORS allow-list carries the three
  // documented dev origins (3000, 5173, 8080). On 3100 every API call from
  // the page is blocked, so a live-mode run sees an empty Explorer.
  webServer: { command: "npx next dev -p 3000 --hostname 127.0.0.1", url: "http://127.0.0.1:3000/explorer", reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_MAPBOX_TOKEN: "", NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN: "", NEXT_TELEMETRY_DISABLED: "1" } },
});
