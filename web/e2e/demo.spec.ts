import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("load sample data and see exceptions", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /sample data/i }).click();
  await expect(page.getByText(/UNMATCHED_WITHDRAWAL|Open exceptions|Needs your attention/i).first()).toBeVisible();
  await page.getByRole("link", { name: /Exceptions/i }).first().click();
  await expect(page.getByText("UNMATCHED_WITHDRAWAL").first()).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
  expect(serious).toEqual([]);
});

test("filter and resolve an exception", async ({ page }) => {
  await page.goto("/exceptions?status=open&severity=low");
  await page.getByText("MISSING_FEE").first().click();
  await page.getByLabel("Note").fill("Fee was waived on the exchange.");
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText(/Marked resolved/i)).toBeVisible();
});

test("export csv", async ({ page }) => {
  await page.goto("/exceptions");
  const download = page.waitForEvent("download");
  await page.goto("/api/v1/export/exceptions.csv");
  const file = await download;
  expect(file.suggestedFilename()).toContain("exceptions");
});
