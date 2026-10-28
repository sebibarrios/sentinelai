import { appAlert, expect, loginAndWait, rows, SAMPLE_DATA, test } from "./fixtures";

test.describe("log upload and detection", () => {
  test.use({ allowedErrors: /status of 409/ }); // the duplicate-upload test provokes one

  test.beforeEach(async ({ page }) => {
    await loginAndWait(page, "analyst");
    await page.goto("/uploads");
  });

  test("bad rows are reported line by line without failing the file", async ({ page }) => {
    await page.locator("#log-file").setInputFiles(`${SAMPLE_DATA}with_errors.csv`);
    const result = page.getByRole("status").filter({ hasText: "with_errors.csv processed" });
    await expect(result).toBeVisible();
    await expect(result.getByText(/^Line \d+:/)).toHaveCount(4);
    await expect(result).toContainText("is not a valid IP address");
  });

  test("a sample log produces alerts, linked to exactly that upload", async ({ page }) => {
    await page.locator("#log-file").setInputFiles(`${SAMPLE_DATA}auth_network_24h.csv`);
    const result = page.getByRole("status").filter({ hasText: "auth_network_24h.csv processed" });
    await expect(result).toBeVisible();
    const created = Number(
      await result.locator("dt", { hasText: "New alerts" }).locator("+ dd").innerText(),
    );
    expect(created).toBeGreaterThan(0);

    await result.getByRole("link", { name: "Review these alerts" }).click();
    await expect(page).toHaveURL(/upload_id=/);
    await expect(page.getByText("Also filtered by")).toBeVisible();
    await expect(rows(page)).toHaveCount(created);

    // Uploading the identical file again is refused rather than duplicating data.
    await page.goto("/uploads");
    await page.locator("#log-file").setInputFiles(`${SAMPLE_DATA}auth_network_24h.csv`);
    await expect(appAlert(page)).toContainText("already uploaded");
  });

  test("files that aren't logs are refused before reaching the server", async ({ page }) => {
    await page.locator("#log-file").setInputFiles({
      name: "invoice.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.7"),
    });
    await expect(appAlert(page)).toHaveText("Choose a .csv, .json, or .ndjson file.");
  });
});

test("dashboard figures drill down into matching alerts and events", async ({ page }) => {
  await loginAndWait(page, "analyst");
  await page.getByRole("link", { name: "High", exact: true }).click();
  await expect(page).toHaveURL(/severity=high/);
  const severities = rows(page).locator("td:first-child");
  await expect(severities.first()).toBeVisible();
  for (const text of await severities.allInnerTexts()) expect(text).toContain("High");

  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Blocked connections" }).click();
  await expect(page).toHaveURL(/category=network&outcome=denied/);
  const outcomes = rows(page).locator("td:nth-child(2)");
  await expect(outcomes.first()).toBeVisible();
  for (const text of await outcomes.allInnerTexts()) expect(text).toBe("denied");
});
