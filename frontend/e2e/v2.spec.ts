import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

/**
 * v2 features at 375 px and 1280 px: the agent's clarifying question and
 * auto-relax (A1), filters (B4), the buyer's verdict and collage on results
 * (B1, A5), the stylist outfit on P8 (B2), auto-tagging (A3), the profile
 * redesign (B3) and /dev/traces (A2). Screenshots for the hand review go to
 * frontend/e2e-shots/ (git-ignored).
 */

const EMAIL = process.env.TEST_USER_EMAIL;
const PASSWORD = process.env.TEST_USER_PASSWORD;
const PHOTO = path.join(__dirname, "..", "..", "backend", "tests", "closet_photos", "6fb65058b860c58310c1cdd686307e40.jpg");
const SHOTS = path.join(__dirname, "..", "e2e-shots");   // git-ignored; Playwright wipes test-results/

const isDesktop = (page: Page) => (page.viewportSize()?.width || 0) >= 768;

async function shot(page: Page, name: string) {
  const width = page.viewportSize()?.width || 0;
  await page.screenshot({ path: path.join(SHOTS, `${width}-${name}.png`), fullPage: true });
}

async function noHorizontalScroll(page: Page) {
  const { scroll, width } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: window.innerWidth,
  }));
  expect(scroll, `page is ${scroll}px wide in a ${width}px window`).toBeLessThanOrEqual(width);
}

async function logIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL!);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD!);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/\/(home|onboarding)/);
}

test.describe("guest (v2)", () => {
  test("a vague request gets one clarifying question (A1)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("something nice")}`);
    await expect(page.getByText("One quick question")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/\?$/);
    await expect(page.locator("article")).toHaveCount(0);
    await shot(page, "clarify");
    await noHorizontalScroll(page);
    await page.getByLabel("Your answer").fill("denim jacket");
    await page.getByRole("button", { name: "Search", exact: true }).last().click();
    await expect(page).toHaveURL(/q=denim\+jacket|q=denim%20jacket/);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
  });

  test("a size nothing matches is relaxed once and the user is told (A1)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("denim jacket size XXS under $50")}`);
    await expect(page.getByText("Nothing matched in size XXS, so I searched every size.")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Best match", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Remove filter size/ })).toHaveCount(0);
    await shot(page, "relaxed");
    await noHorizontalScroll(page);
  });

  test("results show the buyer's verdict, caption copy and outfit board (B1, A5)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("flannel shirt under $40")}`);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    const verdict = page.getByRole("region", { name: /buyer's verdict/ });
    await expect(verdict).toBeVisible();
    await expect(verdict.getByText("Original retail")).toBeVisible();
    await expect(verdict.getByText(/AI estimate|Unknown/).first()).toBeVisible();
    await expect(verdict.getByRole("button", { name: "Copy caption" })).toBeVisible();
    await shot(page, "results-verdict");
    await noHorizontalScroll(page);
  });

  test("filters: phone sheet / desktop chips; location disabled with the reason (B4)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("vintage graphic tee")}`);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    if (isDesktop(page)) {
      const bar = page.getByRole("group", { name: "Filters" });
      await expect(bar.getByRole("button", { name: /Location/ })).toBeDisabled();
      await expect(page.locator("span", { hasText: "Location: Not available for these stores." }).last()).toBeVisible();
      await bar.getByRole("button", { name: /^Store/ }).click();
      await page.getByRole("dialog", { name: "Store filter" }).getByRole("button", { name: "Depop" }).click();
      await shot(page, "filters-open");
      await page.getByRole("button", { name: "Apply" }).click();
    } else {
      await page.getByRole("button", { name: /^Filters/ }).click();
      const sheet = page.getByRole("dialog", { name: "Filters" });
      await expect(sheet).toBeVisible();
      await expect(sheet.getByText("Not available for these stores.")).toBeVisible();
      await expect(sheet.locator("select")).toBeDisabled();
      await sheet.getByRole("button", { name: "Depop" }).click();
      await shot(page, "filters-open");
      await noHorizontalScroll(page);
      await sheet.getByRole("button", { name: "Show results" }).click();
    }
    await expect(page).toHaveURL(/stores=depop/);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    const stores = await page.locator("article").getByText(/Depop|eBay|Poshmark|Mercari/).allInnerTexts();
    expect(stores.join(" ")).not.toMatch(/eBay|Poshmark|Mercari/);
    await noHorizontalScroll(page);
  });
});

test.describe("signed in (v2)", () => {
  test.skip(!EMAIL || !PASSWORD, "TEST_USER_EMAIL / TEST_USER_PASSWORD not set");

  test("profile: grouped cards, Women, sizes, 16 styles, colour row, budget range (B3)", async ({ page }) => {
    await logIn(page);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Shopping for" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Women", exact: true })).toHaveAttribute("aria-pressed", "true");
    for (const h of ["Your sizes (US)", "Body measurements (optional)", "Fit preference", "Styles you like", "Colours you wear most", "Budget per item"]) {
      await expect(page.getByRole("heading", { name: h })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Dresses" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Quiet luxury / old money" })).toBeVisible();
    await expect(page.getByRole("button", { name: "burgundy" })).toBeVisible();
    await expect(page.getByRole("spinbutton", { name: "Min", exact: true })).toHaveValue("10");
    await page.getByRole("button", { name: "Centimeters" }).click();
    await expect(page.getByText("cm").first()).toBeVisible();
    await shot(page, "profile");
    await noHorizontalScroll(page);
    if (isDesktop(page)) {
      // one row of swatches on desktop
      const tops = await page
        .getByRole("region", { name: "Colours you wear most" })
        .getByRole("button")
        .evaluateAll((els) => new Set(els.map((e) => Math.round(e.getBoundingClientRect().top))).size);
      expect(tops).toBe(1);
    }
    // Men hides dresses (not saved)
    await page.getByRole("button", { name: "Men", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Dresses" })).toHaveCount(0);
  });

  test("closet item detail shows the stylist's outfit with a collage (B2, A5)", async ({ page }) => {
    await logIn(page);
    await page.goto("/closet");
    await page.getByRole("link", { name: "Grey pleated midi skirt" }).first().click();
    await expect(page.getByRole("heading", { name: "Finds that go with this" })).toBeVisible();
    await expect(page.getByText("Styled for you")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("group", { name: /Outfit collage/ })).toBeVisible();
    const pieces = page.locator("article ul > li");
    expect(await pieces.count()).toBeGreaterThanOrEqual(2);
    // every piece is either a real listing (View on …) or a "Search this" description
    const views = await page.getByRole("link", { name: /^View on / }).count();
    const searches = await page.getByRole("link", { name: "Search this" }).count();
    expect(views + searches).toBe(await pieces.count());
    await shot(page, "item-outfit");
    await noHorizontalScroll(page);
  });

  test("adding a photo pre-fills the details with AI-suggested badges (A3)", async ({ page }) => {
    await logIn(page);
    await page.goto("/closet/new");
    await page.getByLabel("Choose a photo from your library").setInputFiles(PHOTO);
    await expect(page.getByText("We filled in what we could see.")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("AI suggested").first()).toBeVisible();
    await expect(page.getByLabel(/^Name/)).not.toHaveValue("");
    await shot(page, "autotag");
    await noHorizontalScroll(page);
    // editing a field removes its badge
    const before = await page.getByText("AI suggested").count();
    await page.getByLabel(/^Name/).fill("My camel jacket");
    await expect(page.getByText("AI suggested")).toHaveCount(before - 1);
  });

  test("home has pre-filled filters; /dev/traces lists agent runs (B4, A2)", async ({ page }) => {
    await logIn(page);
    await page.goto("/home");
    await expect(page.getByText(/Pre-filled from your profile/).filter({ visible: true }).first()).toBeVisible();
    if (isDesktop(page)) await expect(page.getByRole("button", { name: /Price: \$10–\$40/ })).toBeVisible();
    await shot(page, "home");
    await noHorizontalScroll(page);
    await page.goto("/dev/traces");
    await expect(page.getByRole("heading", { name: "Agent traces" })).toBeVisible();
    await expect(page.getByText(/model calls/).first()).toBeVisible({ timeout: 30_000 });
    await shot(page, "traces");
    await noHorizontalScroll(page);
  });
});
