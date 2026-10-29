import { API_URL, expect, loginAndWait, rows, test } from "./fixtures";

test.describe("role-based access", () => {
  test.use({ allowedErrors: /status of 403/ }); // the admin-page check provokes one

  test("viewers can read but see no controls that change data", async ({ page }) => {
    await loginAndWait(page, "viewer");

    await page.goto("/incidents");
    await expect(rows(page).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "New incident" })).toHaveCount(0);

    await page.goto("/uploads");
    await expect(page.getByRole("heading", { name: "Upload history" })).toBeVisible();
    await expect(page.getByText("Drop a log file here")).toHaveCount(0);

    await page.goto("/alerts?rule_id=NET-001&status=all");
    await rows(page).first().click();
    await expect(page.getByRole("heading", { name: "Verified finding" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Promote to incident" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Explain this alert" })).toHaveCount(0);

    // Hidden buttons are only cosmetic: the API itself refuses the admin endpoint.
    await page.goto("/admin/users");
    await expect(page.getByText("Your role doesn't have access to this.")).toBeVisible();
  });

  test("admins can grant analyst access", async ({ page }) => {
    await loginAndWait(page, "admin");
    await page.goto("/admin/users");
    const row = rows(page).filter({ hasText: "viewer@sentinel.demo" });
    await row.getByLabel(/Role for/).click();
    await page.getByRole("option", { name: "Analyst" }).click();
    await expect(page.getByText("Updated Riley Viewer")).toBeVisible();
    // Your own row can't be demoted (prevents locking out the last admin).
    const self = rows(page).filter({ hasText: "admin@sentinel.demo" });
    await expect(self.getByLabel(/Role for/)).toBeDisabled();
  });
});

test.describe("security controls", () => {
  test("pages send a Content-Security-Policy and the app runs under it", async ({ page }) => {
    const response = await page.goto("/login");
    const csp = response!.headers()["content-security-policy"];
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("connect-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(response!.headers()["x-frame-options"]).toBe("DENY");

    // Visit every main page; the console guard fails the test on any CSP violation.
    await loginAndWait(page, "analyst");
    for (const path of ["/dashboard", "/alerts", "/incidents", "/events", "/uploads", "/settings"]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
    }
  });

  test("the API refuses calls that bypass the web app", async ({ request }) => {
    const direct = await request.get(`${API_URL}/api/v1/alerts/rules`);
    expect(direct.status()).toBe(403);
    expect((await direct.json()).error.code).toBe("direct_access_forbidden");
    // A forged secret header doesn't help.
    const forged = await request.get(`${API_URL}/api/v1/alerts/rules`, {
      headers: { "X-Sentinel-Proxy-Secret": "guess" },
    });
    expect(forged.status()).toBe(403);
    // The host's health check stays reachable.
    expect((await request.get(`${API_URL}/api/v1/health`)).status()).toBe(200);
  });

  test("state-changing requests without the CSRF header are refused", async ({ page }) => {
    await loginAndWait(page, "analyst");
    const r = await page.request.post("/api/v1/incidents", {
      data: { title: "Forged by another site", severity: "low" },
    });
    expect(r.status()).toBe(403);
    expect((await r.json()).error.code).toBe("csrf_header_missing");
  });

  test("oversized uploads get a clear 413 through the web app, not a server error", async ({ page }) => {
    await loginAndWait(page, "analyst");
    const upload = (megabytes: number) =>
      page.request.post("/api/v1/uploads", {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        multipart: {
          file: { name: "big.csv", mimeType: "text/csv", buffer: Buffer.alloc(megabytes * 1024 * 1024, "a") },
        },
      });
    // Refused by the API's exact 10 MB limit, after passing the proxy intact.
    const overApiLimit = await upload(10.5);
    expect(overApiLimit.status()).toBe(413);
    expect((await overApiLimit.json()).error.code).toBe("payload_too_large");
    // Refused by the web proxy before it buffers the body.
    const huge = await upload(12);
    expect(huge.status()).toBe(413);
    expect((await huge.json()).error.code).toBe("payload_too_large");
  });

  test("layouts fit a phone screen without sideways scrolling", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAndWait(page, "analyst");
    for (const path of ["/dashboard", "/alerts", "/incidents", "/events", "/uploads"]) {
      await page.goto(path);
      await expect(page.locator("main h1")).toBeVisible();
      const width = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(width, path).toBeLessThanOrEqual(390);
    }
  });
});
