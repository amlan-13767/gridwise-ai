// Loads E2E_EMAIL / E2E_PASSWORD from the process environment or from the gitignored file frontend/.env.e2e.
// Credentials are never printed, committed or sent anywhere except the login form of the target site.
import fs from "node:fs";
import path from "node:path";
export function loadE2eEnv() {
  const f = path.join(__dirname, "..", ".env.e2e");
  if (!fs.existsSync(f)) return;
  for (const line of fs.readFileSync(f, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}
