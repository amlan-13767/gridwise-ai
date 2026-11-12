import { Page, expect } from "@playwright/test";
import { loadE2eEnv } from "./env";
loadE2eEnv();
export const PW = process.env.E2E_PASSWORD || process.env.E2E_DEMO_PASSWORD || "Gridwise#Demo1";
export async function login(page: Page, email = process.env.E2E_EMAIL || "admin@gridwise.demo") {
  await page.goto("/login");
  await page.fill("#email", email); await page.fill("#password", PW);
  await page.click("button[type=submit]");
  await expect(page).toHaveURL(/dashboard/);
}
