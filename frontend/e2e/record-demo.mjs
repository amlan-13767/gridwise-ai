// GRIDWISE AI - silent demonstration recorder (Playwright video, no audio).
// Local:      BASE_URL=http://localhost:3000 node e2e/record-demo.mjs
// Production: BASE_URL=https://gridwise-ai-xi.vercel.app E2E_EMAIL=... E2E_PASSWORD=... node e2e/record-demo.mjs
// Drives the REAL running application with real mouse movement and clicks. Data shown is SIMULATED.
import { chromium } from "@playwright/test";
import fs from "node:fs";
for (const line of (fs.existsSync(new URL("../.env.e2e", import.meta.url)) ? fs.readFileSync(new URL("../.env.e2e", import.meta.url), "utf8") : "").split(/\r?\n/)) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/); if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
}
const PROD = !!process.env.E2E_EMAIL;  // production run: read-only (no approvals / status changes / new optimisation runs)

const BASE = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.env.OUT_DIR || "../demo/raw";
fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: OUT, size: { width: 1440, height: 900 } }, acceptDownloads: true });
const page = await ctx.newPage();

// visible, unobtrusive cursor (follows the real mouse events)
await ctx.addInitScript(() => {
  const add = () => {
    if (document.getElementById("__cur")) return;
    const c = document.createElement("div"); c.id = "__cur";
    c.style.cssText = "position:fixed;z-index:2147483647;pointer-events:none;width:22px;height:22px;left:-50px;top:-50px;transition:transform .05s linear";
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 10.8z" fill="#0b1730" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    window.addEventListener("mousemove", (e) => { c.style.left = e.clientX - 3 + "px"; c.style.top = e.clientY - 2 + "px"; }, true);
  };
  if (document.readyState !== "loading") add(); else document.addEventListener("DOMContentLoaded", add);
});

const wait = (ms) => page.waitForTimeout(ms);
let mx = 720, my = 450;
async function glide(x, y, steps = 28) {
  for (let i = 1; i <= steps; i++) {
    const t = i / steps, e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // ease in-out
    await page.mouse.move(mx + (x - mx) * e + Math.sin(t * Math.PI) * 4, my + (y - my) * e);
    await page.waitForTimeout(12);
  }
  mx = x; my = y;
}
async function center(loc) { await loc.scrollIntoViewIfNeeded(); const b = await loc.boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; }
async function hover(loc) { const [x, y] = await center(loc); await glide(x, y); }
async function click(loc, after = 1200) { const [x, y] = await center(loc); await glide(x, y); await wait(250); await page.mouse.click(x, y); await wait(after); }
async function choose(label, value, after = 1800) { const s = page.getByLabel(label, { exact: true }).first(); const [x, y] = await center(s); await glide(x, y); await wait(300); await s.selectOption(value); await wait(after); }
async function scroll(dy, ms = 900) { for (let i = 0; i < 6; i++) { await page.mouse.wheel(0, dy / 6); await wait(ms / 6); } await wait(400); }
const nav = (name) => click(page.getByRole("link", { name, exact: true }).first(), 2500);
const top = async () => { await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" })); await wait(800); };

// 1-2 Landing
await page.goto(BASE); await wait(3200);
await scroll(500); await wait(1500); await top();
await click(page.getByTestId("cta-login"), 1500);
// 3 Login as administrator (password field is masked; demo account, simulated environment)
if (process.env.E2E_EMAIL && process.env.E2E_PASSWORD) {
  // production run: credentials come from the environment, typed into the (masked) password field; never written anywhere
  await click(page.locator("#email"), 300); await page.keyboard.type(process.env.E2E_EMAIL, { delay: 70 });
  await click(page.locator("#password"), 300); await page.keyboard.type(process.env.E2E_PASSWORD, { delay: 70 }); await wait(600);
} else {
  await click(page.getByTestId("demo-administrator"), 1200); // local demo accounts only
}
await click(page.getByRole("button", { name: "Sign in" }), process.env.E2E_EMAIL ? 25000 : 3500); // production free tier may need to wake up
await page.getByTestId("kpi").first().waitFor({ timeout: 90000 });
// 4-5 Dashboard KPIs
await hover(page.getByTestId("kpi").first()); await wait(1800);
await hover(page.getByTestId("kpi").nth(3)); await wait(1500);
// 6 zones
for (const z of ["Academic", "Hostel", "Residential", "all"]) { await choose("Zone", z, 2200); }
// 7 charts
await click(page.getByRole("tab", { name: "Hourly" }), 2000);
await click(page.getByRole("tab", { name: "Weekly" }), 2000);
await click(page.getByRole("tab", { name: "Daily" }), 1500);
await scroll(520, 1200); await wait(2000); await scroll(520, 1200); await wait(2500); await top();
// 8-10 Map -> academic building -> analytics
await nav("Energy Map"); await wait(2500);
await click(page.getByRole("tab", { name: "Academic" }), 2000);
const markers = page.locator(".leaflet-interactive"); await markers.first().waitFor();
await click(markers.nth(2), 3500);
await scroll(300, 800); await wait(1500);
await click(page.getByRole("link", { name: "Open building analytics" }), 3500);
await scroll(600, 1200); await wait(2500); await scroll(600, 1200); await wait(2500); await top();
// 11-12 Forecast
await nav("Demand Forecasting"); await wait(3000);
await choose("Horizon", "7_days", 3000); await choose("Horizon", "24_hours", 2500);
await scroll(500, 1000); await wait(3000); await top();
// 13-14 Anomalies
await nav("Anomaly Detection"); await wait(2000);
await click(page.getByTestId("anomaly-row").first(), 3500);
if (!PROD) await click(page.getByRole("button", { name: "Mark investigating" }), 2500); else await wait(2500);
// 15-16 Cooling
await nav("Cooling Intelligence"); await wait(2500);
await scroll(350, 800);
await click(page.getByTestId("optimize-btn").first(), 4000);
await scroll(450, 1000); await wait(3500); await top();
// 17-18 Renewable
await nav("Renewable Energy"); await wait(3000);
await scroll(450, 1000); await wait(2500); await scroll(450, 1000); await wait(2500); await top();
// 19-20 Optimization
await nav("Optimization Engine"); await wait(2000);
if (!PROD) await click(page.getByTestId("run-opt"), 4000); else await wait(3000);
await scroll(450, 1000); await wait(3500); await scroll(450, 1000); await wait(2500); await top();
// 21 Recommendations
await nav("AI Recommendations"); await wait(3000);
await scroll(350, 800); await wait(1500);
if (!PROD) await click(page.getByTestId("approve-rec").first(), 3000); else await wait(2500);
await top();
// 22 Sustainability
await nav("Sustainability"); await wait(4000); await scroll(400, 900); await wait(2500); await top();
// 23-24 Reports + CSV
await nav("Reports & Exports"); await wait(3500);
await choose("Report", "buildings", 2500);
const dl = page.waitForEvent("download");
await click(page.getByTestId("export-csv"), 500); await dl; await wait(3500);

await ctx.close(); await browser.close();
console.log("recorded to", OUT);
