import { test } from "@playwright/test";
import { login } from "./helpers";
const SHOTS: [string, string][] = [["/dashboard", "dashboard"], ["/map", "map"], ["/hostel", "hostel"], ["/forecast", "forecast"], ["/anomalies", "anomalies"], ["/cooling", "cooling"], ["/renewable", "renewable"], ["/optimization", "optimization"], ["/recommendations", "recommendations"], ["/sustainability", "sustainability"]];
test("screenshots", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/"); await page.screenshot({ path: "../demo/screenshots/landing.png" });
  await login(page);
  for (const [p, n] of SHOTS) { await page.goto(p); await page.waitForLoadState("networkidle"); await page.waitForTimeout(1200); await page.screenshot({ path: `../demo/screenshots/${n}.png`, fullPage: n === "dashboard" }); }
});
