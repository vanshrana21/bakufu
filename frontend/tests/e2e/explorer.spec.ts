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

// These specs run with no backend (see playwright.config.ts). The Explorer must
// then draw the ten MOIL mines from the reference snapshot of GET /mines, and
// say plainly that the surface, the targets and every score need the model:
// nothing is drawn or scored in their place.
test("Explorer draws the real mines, states what needs the model, and invents nothing", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explorer");
  await expect(page.getByText("Map token required")).toBeVisible();
  const map = page.getByTestId("map-render-state");
  await expect(map).toHaveAttribute("data-ready", "true");

  // No backend: no synthetic surface stands in for the model's.
  await expect(map).toHaveAttribute("data-rendered-cells", "0");
  await expect(page.getByText("No model surface: this build has no backend configured", { exact: false })).toBeVisible();
  await expect(page.getByText("Targets are ranked by the live model", { exact: false })).toBeVisible();
  await expect(page.locator(".target-row")).toHaveCount(0);

  // Ten operating mines, as markers and as a roster.
  await expect(map).toHaveAttribute("data-rendered-markers", "10");
  await expect(page.locator(".map-marker--mine")).toHaveCount(10);
  await expect(page.locator(".map-marker--target")).toHaveCount(0);
  await expect(page.locator('[data-testid^="mine-"]')).toHaveCount(10);
  const legend = page.getByLabel("Prospectivity legend");
  await expect(legend.getByText("MOIL mine")).toBeVisible();
  await expect(legend.getByText("Model target")).toBeVisible();

  // No demonstration site survives anywhere on the page.
  await expect(page.getByText(/demo waste|slag heap|ghost reserve|synthetic inventory/i)).toHaveCount(0);

  // A marker selects its mine; the inspector names it and scores nothing.
  const inspector = page.getByRole("complementary", { name: "Selection inspector" });
  await page.locator('.map-marker[data-marker-id="Ukwa"] .map-marker-icon').click();
  await expect(inspector.getByRole("heading", { name: "Ukwa", exact: true })).toBeVisible();
  await expect(page.locator('.map-marker[data-marker-id="Ukwa"]')).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("mine-ukwa")).toHaveAttribute("aria-pressed", "true");
  await expect(inspector.getByText("Scoring a coordinate needs the live model", { exact: false })).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveCount(0);

  // Empty ground is not a place: the map says how to inspect one instead.
  await map.click({ position: { x: 40, y: 260 } });
  await expect(page.getByText("Scoring an arbitrary coordinate needs a point query.", { exact: false })).toBeVisible();

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await settle(page);
  await page.screenshot({ path: "test-results/explorer-1080p.png", fullPage: true });
  await page.setViewportSize({ width: 1366, height: 768 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await settle(page);
  await page.screenshot({ path: "test-results/explorer-1366.png", fullPage: true });
  expect(errors).toEqual([]);
});
