import { expect, test } from "@playwright/test";

test("Selection, masks and the inspector keep their independent truth states", async ({ page }) => {
  await page.goto("/explorer");
  const inspector = page.getByRole("complementary", { name: "Selection inspector" });
  // Nothing is preselected: the inspector waits for a choice.
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();

  await page.getByTestId("mine-balaghat").click();
  await expect(inspector.getByRole("heading", { name: "Balaghat", exact: true })).toBeVisible();
  await expect(inspector.getByText("Balaghat, Madhya Pradesh · underground")).toBeVisible();
  await expect(inspector.getByText("geological mask", { exact: true })).toBeVisible();
  // Without the model there is no score to show, and none is made up.
  await expect(inspector.getByText("Scoring a coordinate needs the live model", { exact: false })).toBeVisible();
  await expect(page.getByTestId("final-score")).toHaveCount(0);

  // The masks change what is inspected under, never what is selected.
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(inspector.getByText("both masks", { exact: true })).toBeVisible();
  await expect(page.getByTestId("mine-balaghat")).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("switch", { name: "Geological", exact: true }).click();
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(inspector.getByText("no mask", { exact: true })).toBeVisible();

  // Rapid selections leave only the last one standing.
  await page.getByTestId("mine-kandri").click();
  await page.getByTestId("mine-tirodi").click();
  await expect(inspector.getByRole("heading", { name: "Tirodi", exact: true })).toBeVisible();
  await expect(page.locator('[data-testid^="mine-"][aria-pressed="true"]')).toHaveCount(1);

  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();
  await expect(page.locator('[data-testid^="mine-"][aria-pressed="true"]')).toHaveCount(0);
});

test("Review register links preserve selected evidence and never create approvals", async ({ page }) => {
  await page.goto("/operations");
  const register = page.getByRole("region", { name: "Review register" });
  await register.getByRole("button", { name: "Proposed 4", exact: true }).click();
  await expect(register.getByRole("row")).toHaveCount(5);
  await expect(register.getByRole("button", { name: "Proposed 4", exact: true })).toHaveAttribute("aria-pressed", "true");
  await register.getByRole("button", { name: "Reviewed 0", exact: true }).click();
  await expect(register.getByRole("row")).toHaveCount(0);
  await expect(register.getByText("No reviewed actions. The demonstration does not fabricate approvals.")).toBeVisible();
  await register.getByRole("button", { name: "All 4", exact: true }).click();
  await register.getByRole("link", { name: "Review slag heap B material suitability" }).click();
  await expect(page).toHaveURL(/\/actions\?review=demo-action-04$/);
  await expect(page.getByRole("heading", { name: "Review slag heap B material suitability", exact: true })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "raw screening score", exact: true })).toBeVisible();
  await page.goto("/actions?review=nonexistent-review");
  await expect(page.getByText("That review ID was not found.", { exact: false })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Review procurement lead times", exact: true })).toBeVisible();
  await expect(page.getByText("Not yet reviewed", { exact: true })).toBeVisible();
});

test("Print includes closed evidence tables and restores the reading state", async ({ page }) => {
  await page.goto("/production");
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
    { label: "Mine Fleet", path: "/mines" },
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
