import { test, expect } from "@playwright/test";

/** Full-page captures must show the settled interface: scroll the document so
 * every entrance reveal fires, then return to the top and let motion finish. */
async function settle(page: import("@playwright/test").Page) {
  await page.evaluate(async () => {
    const step = Math.round(window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 60)));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(700);
}


/** These assertions describe the demonstration fixtures: a four-row review
 * register, a 32% shortfall and dated example months. With the API configured
 * the same pages read from the backend, where shortfall risk is low, no
 * corrective actions are recommended and the register is empty — so there is
 * nothing here to assert. Run with NEXT_PUBLIC_API_BASE_URL unset to exercise
 * them. */
async function skipUnlessFixtureMode(page: import("@playwright/test").Page) {
  const fixtures = await page.getByText("Demonstration fixtures · no API configured").count();
  test.skip(fixtures === 0, "Fixture-content spec; the API is configured, so this page is live.");
}

test("Briefing keeps uncertainty, horizon and demo provenance visible", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/operations");
  await skipUnlessFixtureMode(page);
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByRole("meter", { name: "Shortfall probability" })).toHaveAttribute("aria-valuenow", "32");
  await expect(page.getByTestId("vital-risk")).toHaveText("32%");
  await expect(page.getByRole("region", { name: "Review register" }).getByRole("row")).toHaveCount(5);
  await expect(page.getByText("All plotted values, including the actual-series example, are synthetic.", { exact: false })).toBeVisible();
  await page.getByText("View production values and bounds").click();
  await expect(page.getByRole("rowheader", { name: "2026-11", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "1 month", exact: true }).click();
  await expect(page.getByRole("rowheader", { name: "2026-11", exact: true })).toHaveCount(0);
  await expect(page.getByRole("rowheader", { name: "2026-09", exact: true })).toBeVisible();
  await expect(page.getByRole("meter", { name: "Shortfall probability" })).toHaveAttribute("aria-valuenow", "32");
  await page.getByRole("tab", { name: "3 months", exact: true }).click();
  await page.getByText("View production values and bounds").click();
  await settle(page);
  await page.screenshot({ path: "test-results/command-center-1080p.png", fullPage: true });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "Corrective Actions", exact: true }).click();
  await expect(page.getByText("Not yet reviewed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Plan waste dump A assay review", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Plan waste dump A assay review", exact: true })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "raw screening score", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reviewed (0)", exact: true }).click();
  await expect(page.getByText("No reviewed actions. The demonstration does not fabricate approvals.")).toBeVisible();
  await page.getByRole("button", { name: "All (4)", exact: true }).click();
  await page.goto("/actions?review=demo-action-04");
  await expect(page.getByRole("heading", { name: "Review slag heap B material suitability", exact: true })).toBeVisible();
  await settle(page);
  await page.screenshot({ path: "test-results/actions-1080p.png", fullPage: true });
  await page.getByRole("link", { name: "Production & Risk", exact: true }).click();
  await expect(page.getByText("Synthetic bounds · coverage untested")).toBeVisible();
  await settle(page);
  await page.screenshot({ path: "test-results/production-1080p.png", fullPage: true });
  await page.goto("/operations");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await settle(page);
  await page.screenshot({ path: "test-results/command-center-mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.evaluate(() => document.querySelectorAll("main details").forEach((detail) => detail.setAttribute("open", "")));
  await page.emulateMedia({ media: "print" });
  await settle(page);
  await page.screenshot({ path: "test-results/command-center-print.png", fullPage: true });
  await expect(page.getByText("Operational briefing", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
