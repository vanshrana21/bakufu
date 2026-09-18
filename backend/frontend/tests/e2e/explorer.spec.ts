import { test, expect } from "@playwright/test";

/** The Explorer in live mode: the ten operating mines and the model's ten
 * greenfield targets on one surface.
 *
 * Scores are not asserted as fixed numbers - they come from the model and move
 * when an artifact or the serving mosaic changes. What must hold is structure:
 * the counts, that a selection explains itself, and that clearing leaves no
 * stale score behind.
 */
/** Live mode does real work on first paint: Next compiles the route, the
 * backend scores the belt, and the target pass refines ten coordinates. The
 * 30s default test timeout caps the per-assertion waits below, so it is raised
 * once for the file. */
test.describe.configure({ timeout: 300_000 });

test("Explorer renders mines and model targets, and explains either", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explorer");

  const map = page.getByTestId("map-render-state");
  await expect(map).toHaveAttribute("data-ready", "true", { timeout: 90_000 });
  await expect(page.getByText("Map token required")).toBeVisible();

  // Ten mines and ten targets, on the map and in the lists beside it. The
  // target ranking refines each coordinate, so the first paint can be slow.
  await expect(page.locator(".map-marker--mine")).toHaveCount(10, { timeout: 240_000 });
  await expect(page.locator(".map-marker--target")).toHaveCount(10, { timeout: 240_000 });
  await expect(page.locator(".target-row")).toHaveCount(10);
  await expect(page.locator("[data-testid^='mine-']")).toHaveCount(10);

  // The demonstration waste inventory is gone from this page entirely.
  await expect(page.locator("text=/ghost reserve|waste dump|slag heap/i")).toHaveCount(0);

  const inspector = page.getByRole("complementary", { name: "Selection inspector" });

  // A target explains itself: coordinate, score, and the drivers behind it.
  await page.locator(".map-marker--target").first().click();
  await expect(inspector.getByText("Model target", { exact: true })).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveText(/^0\.\d\d$/, { timeout: 90_000 });
  await inspector.getByRole("tab", { name: "Why?", exact: true }).click();
  await expect(inspector.getByText("Numeric explanation values")).toBeVisible();

  // And so does a mine, selected from the roster.
  await page.getByTestId("mine-balaghat").click();
  await expect(inspector.getByRole("heading", { name: "Balaghat", exact: true })).toBeVisible();
  await expect(inspector.getByText("Operating mine", { exact: true })).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveText(/^0\.\d\d$/, { timeout: 90_000 });

  // Clearing must empty the panel, never leave the previous score standing.
  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await expect(inspector.getByRole("heading", { name: "Inspect a location" })).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveCount(0);

  // A target row carries a navigable coordinate.
  await page.getByTestId("target-t1").click();
  await expect(page.getByRole("link", { name: /Open in Maps/ })).toBeVisible();
  await expect(page.getByText(/^\d\d\.\d{4}, \d\d\.\d{4}$/)).toBeVisible();

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1366, height: 768 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("Masks re-score the surface beneath the markers", async ({ page }) => {
  await page.goto("/explorer");
  const map = page.getByTestId("map-render-state");
  await expect(map).toHaveAttribute("data-ready", "true", { timeout: 90_000 });

  // Geological is the default: it is the mask the target ranking runs under.
  await expect(page.getByRole("switch", { name: "Geological", exact: true })).toBeChecked();
  await expect(page.getByRole("switch", { name: "5km buffer", exact: true })).not.toBeChecked();
  await expect(page.getByText(/geological masks/)).toBeVisible();

  // Adding the buffer keeps only ground near a confirmed occurrence, which is
  // precisely what the greenfield targets sit outside of.
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(page.getByText(/both masks/)).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".map-marker--target")).toHaveCount(10, { timeout: 240_000 });
});
