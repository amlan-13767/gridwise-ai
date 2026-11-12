import { test, expect } from "@playwright/test";
import { login } from "./helpers";

const PAGES: [string, string][] = [
  ["/dashboard", "Campus Energy Command Centre"], ["/map", "Campus Energy Map"], ["/academic", "Academic Area Energy"], ["/hostel", "Hostel Area Energy"],
  ["/residential", "Residential Area Energy"], ["/forecast", "Energy Demand Forecasting"], ["/anomalies", "Anomaly Detection"], ["/cooling", "Cooling Intelligence"],
  ["/renewable", "Renewable Energy"], ["/optimization", "Optimization Engine"], ["/recommendations", "AI Recommendations"], ["/sustainability", "Sustainability Analytics"],
  ["/reports", "Reports & Exports"], ["/iot", "IoT Device Management"], ["/models", "Model Management"], ["/users", "User Management"], ["/settings", "System Configuration"],
];

test("landing page and login errors", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Monitor. Predict. Optimize./ })).toBeVisible();
  await page.getByTestId("cta-login").click();
  await page.fill("#email", "admin@gridwise.demo"); await page.fill("#password", "wrong");
  await page.click("button[type=submit]");
  await expect(page.getByText("Invalid email or password")).toBeVisible();
});

test("unauthenticated users are redirected", async ({ page }) => {
  await page.goto("/dashboard"); await expect(page).toHaveURL(/login/);
});

test("every page renders without console errors (admin)", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|tile\.openstreetmap|ERR_BLOCKED|net::ERR/.test(m.text())) errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await login(page);
  for (const [path, title] of PAGES) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: title, exact: false }).first()).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("sim-banner")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(page.locator("[role=alert]").filter({ hasText: /\S/ })).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test("dashboard shows KPIs and filters work", async ({ page }) => {
  await login(page);
  await expect(page.getByTestId("kpi")).toHaveCount(8);
  await expect(page.getByText("Total consumption")).toBeVisible();
  const before = await page.getByTestId("kpi").first().innerText();
  await page.getByLabel("Zone").first().selectOption("Hostel");
  await page.waitForTimeout(1200);
  const after = await page.getByTestId("kpi").first().innerText();
  expect(after).not.toEqual(before);
  await page.getByRole("tab", { name: "Hourly" }).click();
  await expect(page.locator(".recharts-wrapper").first()).toBeVisible();
});

test("viewer cannot see users page nor residential building data", async ({ page }) => {
  await login(page, "viewer@gridwise.demo");
  await expect(page.getByRole("link", { name: "User Management" })).toHaveCount(0);
  await page.goto("/residential");
  await expect(page.getByText(/withheld for privacy/)).toBeVisible();
});

test("anomaly review, optimisation run and CSV export", async ({ page }) => {
  await login(page);
  await page.goto("/anomalies");
  await page.getByTestId("anomaly-row").first().click();
  await page.getByRole("button", { name: "Mark investigating" }).click();
  await expect(page.getByText("Review saved")).toBeVisible();
  await page.goto("/optimization");
  await page.getByTestId("run-opt").click();
  await expect(page.getByText("Baseline vs optimised grid demand")).toBeVisible({ timeout: 30_000 });
  await page.goto("/reports");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-csv").click()]);
  expect(dl.suggestedFilename()).toMatch(/\.csv$/);
});
