import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { recommendationFixture } from "../src/test/fixtures";

async function chooseLocality(page: Page) {
  await page.getByRole("combobox", { name: /Location/ }).fill("Bana");
  await page.getByRole("option", { name: /Banashankari/ }).click();
  await page.getByLabel("Minimum rating").selectOption("any");
  await expect(page.getByRole("button", { name: /Find Restaurants/i })).toBeEnabled();
}

test("AI-assisted and fallback responses share accessible result cards", async ({ page }, testInfo) => {
  let mode: "llm_assisted" | "deterministic_fallback" = "llm_assisted";
  await page.route("**/api/v1/recommendations", (route) => route.fulfill({ json: {
    ...recommendationFixture, meta: { ...recommendationFixture.meta, ranking_mode: mode },
    summary: mode === "llm_assisted" ? "These choices match your selected filters. Confirm current details with the restaurant." : null,
  } }));
  await page.goto("/");
  await chooseLocality(page);
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByText(/AI-assisted ordering/)).toBeVisible();
  await expect(page.getByText(/These choices match your selected filters/)).toBeVisible();
  await expect(page.getByRole("article")).toHaveCount(2);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("ai-assisted.png"), fullPage: true });
  mode = "deterministic_fallback";
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByText(/AI assistance is unavailable/)).toBeVisible();
  await expect(page.getByText(/These choices match your selected filters/)).toHaveCount(0);
  await expect(page.getByRole("article")).toHaveCount(2);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("fallback.png"), fullPage: true });
});

test("complete search and explicit refinement use the real API", async ({ page }) => {
  await page.goto("/");
  await chooseLocality(page);
  await page.getByRole("checkbox", { name: "Chinese", exact: true }).check();
  await page.getByLabel(/Additional preferences/).fill("family-friendly");
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByRole("heading", { name: "2 restaurants match your preferences" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Spice Elephant", exact: true })).toBeVisible();
  await expect(page.getByText("Not verified by the dataset").first()).toBeVisible();
  await page.getByRole("radio", { name: /Low/ }).check();
  await expect(page.getByText("Preferences changed. Search again to update this shortlist.")).toBeVisible();
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByRole("heading", { name: "No exact matches this time." })).toBeVisible();
  let requests = 0;
  page.on("request", (request) => { if (request.url().includes("/recommendations")) requests++; });
  await page.getByRole("button", { name: "Try any cuisine" }).click();
  await expect(page.getByRole("checkbox", { name: "Chinese", exact: true })).not.toBeChecked();
  expect(requests).toBe(0);
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByRole("heading", { name: "Sea Green Cafe", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cuppa", exact: true })).toBeVisible();
  expect(requests).toBe(1);
  await page.getByText("About these recommendations").click();
  await expect(page.getByText("Applied filter relaxations: None.")).toBeVisible();
});

test("keyboard search, accessibility and responsive results", async ({ page }, testInfo) => {
  await page.goto("/");
  const firstAudit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(firstAudit.violations).toEqual([]);
  const location = page.getByRole("combobox", { name: /Location/ });
  await location.focus();
  await location.fill("Banash");
  await expect(page.getByRole("option", { name: /Banashankari/ })).toBeVisible();
  await location.press("ArrowDown");
  await location.press("Enter");
  await expect(location).toHaveValue("Banashankari");
  await location.press("Tab");
  await expect(page.getByRole("radio", { name: /Medium/ })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: /High/ })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Set my own maximum" })).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("radio", { name: /Medium/ })).toBeChecked();
  await expect(page.getByRole("searchbox", { name: "Search cuisines" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("searchbox", { name: "Search cuisines" })).toBeFocused();
  const cuisines = page.getByRole("checkbox");
  for (let index = 0; index < await cuisines.count(); index++) {
    await page.keyboard.press("Tab");
    await expect(cuisines.nth(index)).toBeFocused();
  }
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Minimum rating")).toBeFocused();
  await page.getByLabel("Minimum rating").selectOption("any");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Number of results")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel(/Additional preferences/)).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: /Find Restaurants/i })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath("keyboard-focus.png"), fullPage: true });
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "3 restaurants match your preferences" })).toBeVisible();
  const resultsAudit = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(resultsAudit.violations).toEqual([]);
  const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(width.scroll).toBeLessThanOrEqual(width.viewport + 1);
  await page.screenshot({ path: testInfo.outputPath("search-results.png"), fullPage: true });
});

test("service and metadata errors recover while preserving selections", async ({ page }) => {
  let failMetadata = true;
  await page.route("**/api/v1/metadata/budget-bands", async (route) => {
    if (failMetadata) { failMetadata = false; await route.fulfill({ status: 503, json: { error: { code: "DATASET_UNAVAILABLE" } } }); }
    else await route.continue();
  });
  await page.goto("/");
  await expect(page.getByRole("alert").filter({ hasText: "Budget options could not load" })).toBeVisible();
  await page.getByRole("button", { name: "Retry options" }).click();
  await chooseLocality(page);
  let failSearch = true;
  await page.route("**/api/v1/recommendations", async (route) => {
    if (failSearch) { failSearch = false; await route.fulfill({ status: 503, json: { error: { code: "DATASET_UNAVAILABLE", request_id: "test-unavailable" } } }); }
    else await route.continue();
  });
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByRole("alert").filter({ hasText: /Restaurant data is temporarily unavailable/ })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /Location/ })).toHaveValue("Banashankari");
  await page.getByRole("button", { name: "Try search again" }).click();
  await expect(page.getByRole("heading", { name: "3 restaurants match your preferences" })).toBeVisible();
});

test("long source text, missing facts and zoom remain usable", async ({ page }, testInfo) => {
  await page.route("**/api/v1/recommendations", (route) => route.fulfill({ json: {
    ...recommendationFixture, recommendations: [{ ...recommendationFixture.recommendations[0],
      name: "<script>Long restaurant name</script> " + "ExtraordinarilyLongRestaurantName".repeat(5),
      cuisines: ["An exceptionally long cuisine name without shortening the source details"],
      rating: null, estimated_cost: null,
    }],
  } }));
  await page.goto("/");
  await chooseLocality(page);
  await page.getByRole("button", { name: /Find Restaurants/i }).click();
  await expect(page.getByText("Rating unavailable")).toBeVisible();
  await expect(page.getByText("Estimated cost unavailable")).toBeVisible();
  await expect(page.locator(".restaurant-card script")).toHaveCount(0);
  if (testInfo.project.name === "chromium") {
    await page.evaluate(() => { document.body.style.zoom = "2"; });
    let dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.viewport + 1);
    await page.evaluate(() => { document.body.style.zoom = "1"; });
    await page.setViewportSize({ width: 320, height: 800 });
    dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.viewport + 1);
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.getByRole("button", { name: /Find Restaurants/i })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("long-content.png"), fullPage: true });
});
