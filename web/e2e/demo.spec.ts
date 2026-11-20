import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const apiBase = "http://127.0.0.1:8000";

test.beforeEach(async ({ request }) => {
  const reset = await request.post(`${apiBase}/api/v1/reset`);
  expect(reset.ok()).toBeTruthy();
});

test("load sample data and see exceptions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Try with sample data" }).click();
  await expect(page.getByText(/UNMATCHED_WITHDRAWAL|Open exceptions|Needs your attention/i).first()).toBeVisible();
  await page.getByRole("link", { name: /Exceptions/i }).first().click();
  await expect(page.locator("tbody tr").filter({ hasText: "UNMATCHED_WITHDRAWAL" }).first()).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
  expect(serious).toEqual([]);
});

test("filter and resolve an exception", async ({ page, request }) => {
  const load = await request.post(`${apiBase}/api/v1/demo/load`);
  expect(load.ok()).toBeTruthy();
  await page.goto("/exceptions?status=open&type=MISSING_FEE");
  await page.locator("tbody tr").filter({ hasText: "MISSING_FEE" }).first().click();
  await page.getByLabel("Note").fill("Fee was waived on the exchange.");
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText(/Marked resolved/i)).toBeVisible();
});

test("export csv", async ({ page, request }) => {
  const load = await request.post(`${apiBase}/api/v1/demo/load`);
  expect(load.ok()).toBeTruthy();
  await page.goto("/exceptions");
  const response = await request.get(`${apiBase}/api/v1/export/exceptions.csv`);
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-disposition"]).toContain("exceptions.csv");
});
