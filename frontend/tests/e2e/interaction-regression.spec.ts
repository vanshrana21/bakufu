import { expect, test } from "@playwright/test";

test("Search, evidence and masks preserve their independent truth states", async ({ page }) => {
  await page.goto("/explorer");
  const search = page.getByRole("textbox", { name: "Search fixture sites, Sandur or Bonai" });
  const inspector = page.getByRole("complementary", { name: "Site inspector" });
  await expect(page.getByTestId("raw-score")).toHaveText("0.84");

  await search.fill("unlisted location");
  await expect(page.getByText("No fixture found. Scope has not been inferred.")).toBeVisible();
  await search.press("Escape");
  await expect(search).toHaveValue("");
  await expect(page.getByTestId("raw-score")).toHaveText("0.84");

  await page.getByRole("switch", { name: "Ghost Reserves", exact: true }).click();
  await search.fill("dump C");
  await page.getByRole("button", { name: "Demo waste dump C · outside buffer Inspect" }).click();
  await expect(page.getByText("This site is outside the Ghost Reserve filter. Turn Ghost Reserves off to inspect it.")).toBeVisible();
  await expect(page.getByTestId("site-demo-dump-c")).toHaveCount(0);
  await expect(page.getByTestId("raw-score")).toHaveText("0.84");

  // Scope queries remain available while the material filter is enabled.
  await search.fill("Sandur");
  await page.getByRole("button", { name: "Sandur Outside scope", exact: true }).click();
  await expect(page.getByTestId("scope-message")).toHaveText("Outside validated scope (Sausar Belt)");
  await expect(page.getByTestId("final-score")).toHaveCount(0);
  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();

  await page.getByTestId("site-demo-slag-b").click();
  await expect(page.getByTestId("raw-score")).toHaveText("0.62");
  await expect(inspector.getByText("Processed slag differs from the geology used for training.", { exact: false })).toBeVisible();
  await page.getByRole("switch", { name: "Geological", exact: true }).click();
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(page.getByTestId("final-score")).toHaveText("0.62");
  await inspector.getByRole("tab", { name: "Constraints", exact: true }).click();
  await expect(inspector.getByText("No screening mask is active.")).toBeVisible();
  await expect(inspector.getByText("Mask inclusion is not environmental approval.", { exact: false })).toBeVisible();
  await expect(page.getByTestId("site-demo-dump-c")).toHaveCount(0);
  await page.getByRole("switch", { name: "Ghost Reserves", exact: true }).click();
  await page.getByTestId("site-farmland-control").click();
  await expect(page.getByTestId("raw-score")).toHaveText("0.99");
  await inspector.getByRole("tab", { name: "Why?", exact: true }).click();
  await expect(inspector.getByText("No numeric SHAP payload was provided for this diagnostic.", { exact: false })).toBeVisible();
});

test("Review register links preserve selected evidence and never create approvals", async ({ page }) => {
  await page.goto("/");
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
  await page.goto("/");
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
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  const routes = [
    { label: "Prospectivity", path: "/explorer" },
    { label: "Production & Risk", path: "/production" },
    { label: "Corrective Actions", path: "/actions" },
    { label: "Command Center", path: "/" },
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
