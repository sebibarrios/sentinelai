import path from "node:path";

import { expect, test as base, type Page } from "@playwright/test";

export const PASSWORD = "SentinelDemo2026"; // seed script's non-production default
export const USERS = {
  admin: { email: "admin@sentinel.demo", name: "Avery Admin" },
  analyst: { email: "analyst@sentinel.demo", name: "Jordan Analyst" },
  viewer: { email: "viewer@sentinel.demo", name: "Riley Viewer" },
} as const;
export const API_URL = "http://localhost:8100"; // direct backend address (see config)
export const SAMPLE_DATA = path.join(__dirname, "..", "..", "sample-data") + path.sep;

/**
 * Every test fails if the page logs an error or a CSP violation, so a policy that
 * silently blocks the app's own scripts or styles can't slip through.
 * Set `allowedErrors` to a pattern for responses a test expects (e.g. a 403 it
 * provokes). It's one RegExp, not an array: Playwright treats an array option value
 * as a [value, options] pair.
 */
export const test = base.extend<{ allowedErrors: RegExp | null; consoleGuard: void }>({
  allowedErrors: [null, { option: true }],
  consoleGuard: [
    async ({ page, allowedErrors }, use) => {
      const problems: string[] = [];
      page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
      page.on("console", (m) => {
        if (m.type() !== "error") return;
        const text = m.text();
        if (!allowedErrors?.test(text)) problems.push(`console: ${text}`);
      });
      await use();
      expect(problems, "unexpected browser errors").toEqual([]);
    },
    { auto: true },
  ],
});
export { expect };

/** Sign in. Pass next=null to use the login page the browser is already on. */
export async function login(page: Page, role: keyof typeof USERS, next: string | null = "") {
  if (next !== null) await page.goto(`/login${next}`);
  await page.getByLabel("Email").fill(USERS[role].email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

export async function loginAndWait(page: Page, role: keyof typeof USERS) {
  await login(page, role);
  await expect(page).toHaveURL(/\/dashboard$/);
}

export async function signOut(page: Page, role: keyof typeof USERS) {
  await page.getByRole("button", { name: new RegExp(USERS[role].name) }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
}

/** The app's own alert messages (not Next.js's hidden route announcer, which is also role=alert). */
export function appAlert(page: Page) {
  return page.locator('[role="alert"]:not(#__next-route-announcer__)');
}

/**
 * Table rows on the current page. Next.js keeps recently visited pages mounted but
 * hidden (React <Activity>), so only visible rows belong to the page on screen.
 */
export function rows(page: Page) {
  return page.locator("main tbody tr:visible");
}
