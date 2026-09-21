import { expect, test } from "@playwright/test";

// Live first paint compiles the route and scores the belt; see explorer.spec.ts.
test.describe.configure({ timeout: 300_000 });

test("Explorer selection and masks keep their independent truth states", async ({ page }) => {
  await page.goto("/explorer");
  const inspector = page.getByRole("complementary", { name: "Selection inspector" });
  await expect(page.locator(".map-marker--target")).toHaveCount(10, { timeout: 240_000 });

  // Nothing is selected until the viewer selects it: the panel must not open
  // on a guess.
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();

  // A mine and a target are different kinds of thing, and the panel says which.
  await page.getByTestId("mine-ukwa").click();
  await expect(inspector.getByText("Operating mine", { exact: true })).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveText(/^0\.\d\d$/, { timeout: 90_000 });
  await page.getByTestId("target-t2").click();
  await expect(inspector.getByText("Model target", { exact: true })).toBeVisible();

  // Switching masks re-scores the selection rather than leaving the old number.
  await page.getByRole("switch", { name: "Geological", exact: true }).click();
  await expect(inspector.getByText(/none mask/)).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("raw-score")).toHaveText(/^0\.\d\d$/, { timeout: 90_000 });

  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();
});

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

test("Review register links preserve selected evidence and never create approvals", async ({ page }) => {
  await page.goto("/operations");
  await skipUnlessFixtureMode(page);
  const register = page.getByRole("region", { name: "Review register" });
  await register.getByRole("link", { name: "Review slag heap B material suitability" }).click();
  await expect(page).toHaveURL(/\/actions\?review=demo-action-04$/);
  await expect(page.getByRole("heading", { name: "Review slag heap B material suitability", exact: true })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "raw screening score", exact: true })).toBeVisible();
  await register.getByRole("button", { name: "Proposed (4)", exact: true }).click();
  await expect(register.getByRole("row")).toHaveCount(5);
  await expect(register.getByRole("button", { name: "Proposed (4)", exact: true })).toHaveAttribute("aria-pressed", "true");
  await register.getByRole("button", { name: "Reviewed (0)", exact: true }).click();
  await expect(register.getByRole("row")).toHaveCount(1);
  await expect(register.getByText("No reviewed actions. The demonstration does not fabricate approvals.")).toBeVisible();
  await page.goto("/actions?review=nonexistent-review");
  await expect(page.getByText("That review ID was not found.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Review procurement lead times", exact: true })).toBeVisible();
  await expect(page.getByText("Not yet reviewed", { exact: true })).toBeVisible();
});

test("Print includes closed evidence tables and restores the reading state", async ({ page }) => {
  await page.goto("/operations");
  await skipUnlessFixtureMode(page);
  const disclosure = page.locator("main details").filter({ has: page.getByText("View production values and bounds", { exact: true }) });
  await expect(disclosure).not.toHaveAttribute("open");
  await page.evaluate(() => {
    window.print = () => { document.documentElement.dataset.printInvoked = "true"; };
  });
  await page.getByRole("button", { name: "Print briefing", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-print-invoked", "true");
  await expect(disclosure).toHaveAttribute("open");
  await expect(page.getByRole("rowheader", { name: "2026-11", exact: true })).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(disclosure).not.toHaveAttribute("open");

  // A table deliberately opened by the user must stay open after printing.
  await disclosure.locator("summary").click();
  await page.evaluate(() => { delete document.documentElement.dataset.printInvoked; });
  await page.getByRole("button", { name: "Print briefing", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-print-invoked", "true");
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(disclosure).toHaveAttribute("open");
});

test("Every workspace view remains navigable at a narrow viewport", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/operations");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  const routes = [
    { label: "Prospectivity", path: "/explorer" },
    { label: "Production & Risk", path: "/production" },
    { label: "Corrective Actions", path: "/actions" },
    { label: "Command Center", path: "/operations" },
    { label: "Assets & Inventory", path: "/assets" },
    { label: "Geologist Feedback", path: "/feedback" },
    { label: "Data Pipeline", path: "/pipeline" },
    { label: "Compliance", path: "/compliance" },
    { label: "Reports & Exports", path: "/reports" },
    { label: "Administration & RBAC", path: "/admin" },
  ];
  for (const route of routes) {
    await page.getByRole("button", { name: "Toggle navigation" }).click();
    await navigation.getByRole("link", { name: route.label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${route.path}$`));
    await expect(page.getByRole("button", { name: "Toggle navigation" })).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator("#workspace-navigation").getByRole("link", { name: route.label, exact: true, includeHidden: true })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `test-results/${route.path.slice(1) || "command-center"}-mobile-regression.png`, fullPage: true });
  }
  expect(errors).toEqual([]);
});
