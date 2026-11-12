// Production verification against the deployed site. Read-only: no approvals, no status changes.
// Run: cd frontend && E2E_BASE_URL=https://gridwise-ai-xi.vercel.app npx playwright test e2e/production.spec.ts
// Authenticated tests need E2E_EMAIL / E2E_PASSWORD (environment or gitignored frontend/.env.e2e) and are skipped otherwise.
import { test, expect, Page } from "@playwright/test";
import { loadE2eEnv } from "./env";
loadE2eEnv();
const SITE = process.env.E2E_BASE_URL || "https://gridwise-ai-xi.vercel.app";
const API = process.env.E2E_API_URL || "https://gridwise-api-9ypw.onrender.com";
const HAVE = !!(process.env.E2E_EMAIL && process.env.E2E_PASSWORD);
test.use({ baseURL: SITE });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login");
  await page.fill("#email", process.env.E2E_EMAIL!); await page.fill("#password", process.env.E2E_PASSWORD!);
  await page.click("button[type=submit]");
  await expect(page.getByTestId("kpi").first()).toBeVisible({ timeout: 90_000 });
}

test.describe("unauthenticated", () => {
  test("API health, docs, CORS and auth guards", async ({ request }) => {
    const h = await (await request.get(`${API}/api/health`, { timeout: 90_000 })).json();
    expect(h).toMatchObject({ status: "ok", environment: "production", database: "ok", simulated_data_loaded: true, first_admin_configured: true });
    expect((await request.get(`${API}/docs`)).status()).toBe(200);
    expect((await request.get(`${API}/api/zones`)).status()).toBe(401);
    expect((await request.get(`${API}/api/energy/overview`)).status()).toBe(401);
    expect((await request.post(`${API}/api/auth/login`, { data: { email: "nobody@example.org", password: "not-a-real-password" } })).status()).toBe(401);
    const pre = await request.fetch(`${API}/api/auth/login`, { method: "OPTIONS", headers: { Origin: SITE, "Access-Control-Request-Method": "POST" } });
    expect(pre.headers()["access-control-allow-origin"]).toBe(SITE);
    const evil = await request.fetch(`${API}/api/auth/login`, { method: "OPTIONS", headers: { Origin: "https://evil.example", "Access-Control-Request-Method": "POST" } });
    expect(evil.headers()["access-control-allow-origin"]).toBeUndefined();
  });
  test("frontend: landing, bad login, redirect, mobile layout", async ({ page }) => {
    await page.goto("/"); await expect(page.getByRole("heading", { name: /Monitor. Predict. Optimize./ })).toBeVisible();
    await page.goto("/dashboard"); await expect(page).toHaveURL(/login/);
    const req = page.waitForRequest((r) => r.url().includes("/api/auth/login"));
    await page.fill("#email", "nobody@example.org"); await page.fill("#password", "not-a-real-password"); await page.click("button[type=submit]");
    expect((await req).url()).toBe(`${API}/api/auth/login`);          // frontend talks to the production API, not localhost
    await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 90_000 });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/"); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    await page.goto("/login"); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  });
});

test.describe("authenticated (administrator)", () => {
  test.skip(!HAVE, "E2E_EMAIL / E2E_PASSWORD not provided");
  const PAGES: [string, string][] = [["/academic", "Academic Area Energy"], ["/hostel", "Hostel Area Energy"], ["/residential", "Residential Area Energy"], ["/map", "Campus Energy Map"],
    ["/forecast", "Energy Demand Forecasting"], ["/anomalies", "Anomaly Detection"], ["/cooling", "Cooling Intelligence"], ["/renewable", "Renewable Energy"],
    ["/optimization", "Optimization Engine"], ["/recommendations", "AI Recommendations"], ["/sustainability", "Sustainability Analytics"], ["/reports", "Reports & Exports"],
    ["/iot", "IoT Device Management"], ["/models", "Model Management"], ["/users", "User Management"], ["/settings", "System Configuration"]];

  test("login, API token and protected endpoints", async ({ page, request }) => {
    await signIn(page);
    await expect(page.getByTestId("kpi")).toHaveCount(8);
    await expect(page.getByTestId("sim-banner")).toContainText("SIMULATED");
    const tok = await page.evaluate(() => localStorage.getItem("gridwise_token"));
    expect(tok && tok.split(".").length).toBe(3);                         // JWT stored
    const auth = { Authorization: `Bearer ${tok}` };
    expect((await request.get(`${API}/api/energy/overview`, { headers: auth })).status()).toBe(200);
    expect((await request.get(`${API}/api/users`, { headers: auth })).status()).toBe(200);
    expect((await request.get(`${API}/api/energy/overview`, { headers: { Authorization: "Bearer tampered.token.value" } })).status()).toBe(401);
  });

  test("every page loads backend data with no errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("response", (r) => { if (r.url().startsWith(API) && r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
    await signIn(page);
    for (const [p, title] of PAGES) {
      await page.goto(p); await expect(page.getByRole("heading", { name: title }).first()).toBeVisible({ timeout: 60_000 });
      await page.waitForLoadState("networkidle");
      await expect(page.locator("[role=alert]").filter({ hasText: /\S/ })).toHaveCount(0);
      await expect(page.getByTestId("sim-banner")).toBeVisible();
    }
    expect(errors).toEqual([]);
  });

  test("dashboard data, filters, charts and zones", async ({ page }) => {
    await signIn(page);
    const total = await page.getByTestId("kpi").first().innerText(); expect(total).toMatch(/kWh/);
    for (const z of ["Academic", "Hostel", "Residential"]) { await page.getByLabel("Zone", { exact: true }).first().selectOption(z); await page.waitForTimeout(1500); await expect(page.locator(".recharts-wrapper").first()).toBeVisible(); }
    await page.getByRole("tab", { name: "Weekly" }).click(); await expect(page.locator(".recharts-area").first()).toBeVisible();
  });

  test("forecast, anomalies, cooling, renewable, optimisation, recommendations", async ({ page }) => {
    await signIn(page);
    await page.goto("/forecast"); await expect(page.getByText("Actual vs predicted demand")).toBeVisible({ timeout: 60_000 }); await expect(page.getByText("Model evaluation")).toBeVisible();
    await page.goto("/anomalies"); await expect(page.getByTestId("anomaly-row").first()).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("anomaly-row").first().click(); await expect(page.getByText(/not confirmed wastage/)).toBeVisible();
    await page.goto("/cooling"); await expect(page.getByTestId("optimize-btn").first()).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("optimize-btn").first().click(); await expect(page.getByText(/ESTIMATE/).first()).toBeVisible({ timeout: 60_000 });
    await page.goto("/renewable"); await expect(page.getByText(/Simulated solar generation/)).toBeVisible({ timeout: 60_000 });
    await page.goto("/optimization"); await expect(page.getByText("Baseline vs optimised grid demand")).toBeVisible({ timeout: 60_000 });
    await page.goto("/recommendations"); await expect(page.getByText("Supporting evidence").first()).toBeVisible({ timeout: 60_000 });
    await page.goto("/sustainability"); await expect(page.getByText(/ESTIMATES/).first()).toBeVisible({ timeout: 60_000 });
  });

  test("map and building analytics", async ({ page }) => {
    await signIn(page);
    await page.goto("/map"); await page.locator(".leaflet-interactive").first().waitFor({ timeout: 60_000 });
    await page.locator(".leaflet-interactive").nth(2).click({ force: true });
    await expect(page.getByRole("link", { name: "Open building analytics" })).toBeVisible({ timeout: 60_000 });   // details load from the API
    await page.getByRole("link", { name: "Open building analytics" }).click();
    await expect(page.getByText("Predicted demand: next 24 hours")).toBeVisible({ timeout: 60_000 });
  });

  test("responsive layout and CSV export", async ({ page }) => {
    await signIn(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard"); await expect(page.getByTestId("kpi").first()).toBeVisible({ timeout: 60_000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/reports"); const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("export-csv").click()]);
    expect(dl.suggestedFilename()).toMatch(/\.csv$/);
  });

  test("logout and expired/invalid session handling", async ({ page }) => {
    await signIn(page);
    await page.evaluate(() => localStorage.setItem("gridwise_token", "expired.or.invalid"));   // simulate an expired session
    await page.goto("/dashboard"); await expect(page).toHaveURL(/login/, { timeout: 60_000 });
    await signIn(page);
    await page.getByRole("button", { name: "Sign out" }).click(); await expect(page).toHaveURL(/login/);
    await page.goto("/dashboard"); await expect(page).toHaveURL(/login/);
  });
});
