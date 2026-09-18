import { expect, test } from "@playwright/test";

/** Every workspace route renders without tripping the error boundary, and
 * without a console or page error. The boundary says nothing about what
 * failed, so a route that trips it is indistinguishable from missing data. */
test.describe.configure({ timeout: 300_000 });

const ROUTES = [
  "/", "/operations", "/mines", "/explorer", "/production", "/actions",
  "/assets", "/feedback", "/pipeline", "/compliance", "/reports", "/admin",
];

for (const route of ROUTES) {
  test(`${route} renders`, async ({ page }) => {
    const problems: string[] = [];
    page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() === "error") problems.push(`console: ${message.text()}`);
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && response.url().includes("/_next/")) {
        problems.push(`${response.status()}: ${new URL(response.url()).pathname}`);
      }
    });
    await page.goto(route, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "This view could not load" })).toHaveCount(0);
    expect(problems, `${route}\n${problems.join("\n")}`).toEqual([]);
  });
}
