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


test("Explorer truth states and mask/selection synchronization", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/explorer");
  await expect(page.getByTestId("raw-score")).toHaveText("0.84");
  await expect(page.getByText("Map token required")).toBeVisible();
  const map = page.getByTestId("map-render-state");
  await expect(map).toHaveAttribute("data-ready", "true");
  await expect(map).toHaveAttribute("data-rendered-cells", "4");
  await expect(map).toHaveAttribute("data-rendered-excluded", "2");
  await expect(map).toHaveAttribute("data-rendered-waste", "3");
  await page.getByRole("switch", { name: "Ghost Reserves", exact: true }).click();
  await expect(page.getByTestId("site-demo-dump-c")).toHaveCount(0);
  await expect(map).toHaveAttribute("data-rendered-cells", "2");
  await expect(map).toHaveAttribute("data-rendered-waste", "2");
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(page.getByTestId("site-demo-dump-c")).toHaveCount(0);
  await page.getByRole("switch", { name: "Ghost Reserves", exact: true }).click();
  await page.getByTestId("site-farmland-control").click();
  await expect(page.getByTestId("final-score")).toHaveText("0.99");
  await expect(map).toHaveAttribute("data-rendered-excluded", "0");
  await page.getByRole("switch", { name: "5km buffer", exact: true }).click();
  await expect(page.getByTestId("raw-score")).toHaveText("0.99");
  await expect(page.getByTestId("final-score")).toHaveText("0.00");
  await expect(map).toHaveAttribute("data-rendered-excluded", "2");
  // Rapid selections must never leave an old masked response in the inspector.
  await page.getByTestId("site-demo-dump-a").click();
  await page.getByTestId("site-demo-slag-b").click();
  await expect(page.getByTestId("raw-score")).toHaveText("0.62");
  const search = page.getByRole("textbox", { name: "Search fixture sites, Sandur or Bonai" });
  await search.fill("Sandur");
  await search.press("Enter");
  await expect(page.getByTestId("scope-message")).toHaveText("Outside validated scope (Sausar Belt)");
  await expect(page.getByTestId("raw-score")).toHaveCount(0);
  await search.fill("Bonai");
  await search.press("Enter");
  await expect(page.getByTestId("scope-message")).toBeVisible();
  await page.getByTestId("site-demo-dump-a").click();
  await page.getByRole("tab", { name: "Why?", exact: true }).click();
  await expect(page.getByText("Numeric explanation values")).toBeVisible();
  await expect(page.getByTestId("raw-score")).toHaveText("0.84");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await settle(page);
  await page.screenshot({ path: "test-results/explorer-1080p.png", fullPage: true });
  await page.setViewportSize({ width: 1366, height: 768 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await settle(page);
  await page.screenshot({ path: "test-results/explorer-1366.png", fullPage: true });
  expect(errors).toEqual([]);
});
