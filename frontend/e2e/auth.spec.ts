import { appAlert, expect, login, loginAndWait, PASSWORD, signOut, test, USERS } from "./fixtures";

test.describe("authentication", () => {
  // Revoked-session checks provoke 401s; the lockout test provokes a 429.
  test.use({ allowedErrors: /status of (401|429)/ });
  test("signed-out visitors are sent to sign in, then back to the page they asked for", async ({
    page,
  }) => {
    await page.goto("/alerts?severity=high");
    await expect(page).toHaveURL(/\/login\?next=/);
    await login(page, "analyst", null); // sign in on the page we were redirected to
    await expect(page).toHaveURL(/\/alerts\?severity=high$/);
    await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();
  });

  test("a crafted next= link can't redirect off-site after sign-in", async ({ page }) => {
    for (const next of ["//evil.example", "/\\evil.example", "https://evil.example/x"]) {
      await page.context().clearCookies();
      await login(page, "analyst", `?next=${encodeURIComponent(next)}`);
      await expect(page).toHaveURL(/^http:\/\/localhost:3100\/dashboard$/);
    }
  });

  test("wrong password shows a generic error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.analyst.email);
    await page.getByLabel("Password").fill("not-the-password-1");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(appAlert(page)).toHaveText("Invalid email or password");
  });

  test("an account locks after repeated failures, with a clear message", async ({ page }) => {
    // A dedicated address, so the lockout can't affect other tests.
    await page.goto("/login");
    const email = page.getByLabel("Email");
    const password = page.getByLabel("Password");
    const submit = page.getByRole("button", { name: "Sign in" });
    await email.fill("lockout-test@sentinel.demo");
    for (let i = 0; i < 5; i++) {
      await password.fill(`wrong-password-${i}`);
      await submit.click();
      await expect(appAlert(page)).toHaveText("Invalid email or password");
    }
    await password.fill(PASSWORD);
    await submit.click();
    await expect(appAlert(page)).toContainText(
      "Too many failed sign-in attempts for this account",
    );
  });

  test("signing out ends the session for real, not just in this tab", async ({ page, context }) => {
    await loginAndWait(page, "analyst");
    const second = await context.newPage(); // same cookie jar, e.g. another tab
    await second.goto("/incidents");
    await expect(second.getByRole("heading", { name: "Incidents" })).toBeVisible();

    const cookie = (await context.cookies()).find((c) => c.name === "sentinel_session")!;
    await signOut(page, "analyst");

    // Replaying the old cookie (as a thief would) no longer works.
    await context.addCookies([cookie]);
    const me = await second.request.get("/api/v1/auth/me");
    expect(me.status()).toBe(401);
  });

  test("new accounts start with read-only access", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Full name").fill("Casey New");
    await page.getByLabel("Email").fill(`casey-${Date.now()}@example.com`);
    await page.getByLabel("Password").fill("Str0ngPassw0rd");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText("Viewer", { exact: true })).toBeVisible();
    await page.goto("/incidents");
    await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();
    await expect(page.getByRole("button", { name: "New incident" })).toHaveCount(0);
  });
});
