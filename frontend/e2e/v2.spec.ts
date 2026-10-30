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

  test("a size nothing matches is dropped and the user is told in one line (A1)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("denim jacket size XXS under $50")}`);
    await expect(page.getByRole("status").filter({ hasText: /searched every size/ })).toBeVisible({ timeout: 60_000 });
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

  test("filters apply instantly: phone sheet / desktop chips; location is FB-only (B4)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("vintage graphic tee")}`);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    if (isDesktop(page)) {
      const bar = page.getByRole("group", { name: "Filters" });
      await expect(bar.getByRole("button", { name: /Location.*Facebook Marketplace/ })).toBeDisabled();
      await bar.getByRole("button", { name: /^Store/ }).click();
      const dialog = page.getByRole("dialog", { name: "Store filter" });
      await expect(dialog.getByRole("button", { name: "Etsy" })).toBeEnabled();
      await dialog.getByRole("button", { name: "Depop" }).click();
      // no Apply button: the URL and the results change at once
      await expect(page).toHaveURL(/stores=depop/);
      await expect(dialog.getByText(/\d+ results?/)).toBeVisible({ timeout: 60_000 });
      await shot(page, "filters-open");
      await dialog.getByRole("button", { name: "Done" }).click();
    } else {
      await page.getByRole("button", { name: /^Filters/ }).click();
      const sheet = page.getByRole("dialog", { name: "Filters" });
      await expect(sheet).toBeVisible();
      await expect(sheet.getByText("Location is for Facebook Marketplace, which isn't connected yet.")).toBeVisible();
      await expect(sheet.getByRole("textbox", { name: /ZIP or city/ })).toBeDisabled();
      await sheet.getByRole("button", { name: "Depop" }).click();
      await expect(page).toHaveURL(/stores=depop/);
      const show = sheet.getByRole("button", { name: /^Show \d+ results?$/ });
      await expect(show).toBeVisible({ timeout: 60_000 });
      await shot(page, "filters-open");
      await noHorizontalScroll(page);
      await show.click();
    }
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    const stores = await page.locator("article").getByText(/Depop|eBay|Poshmark|Mercari|Etsy/).allInnerTexts();
    expect(stores.join(" ")).not.toMatch(/eBay|Poshmark|Mercari|Etsy/);
    // a refresh keeps the filter
    await page.reload();
    await expect(page).toHaveURL(/stores=depop/);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    await noHorizontalScroll(page);
  });

  test("removing a chip updates the results at once (B4)", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("flannel shirt under $40")}`);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Remove filter under $40" }).click();
    await expect(page).toHaveURL(/no_price=1/);
    await expect(page.getByRole("button", { name: "Remove filter under $40" })).toHaveCount(0, { timeout: 60_000 });
    await expect(page.getByText("Best match", { exact: true })).toBeVisible();
  });

  test("size guide (B3)", async ({ page }) => {
    await page.goto("/size-guide");
    await expect(page.getByRole("heading", { name: "Size guide (US)" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tops & dresses" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Dress shirts" })).toBeVisible();
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
    // US retail sizes for Women: size range tabs, compact groups, a size guide
    for (const r of ["Regular", "Petite", "Plus"]) await expect(page.getByRole("radio", { name: r })).toBeVisible();
    await expect(page.getByText("Tops & dresses", { exact: true })).toBeVisible();
    await expect(page.getByText("Jeans · waist", { exact: true })).toBeVisible();
    await expect(page.getByText("Shoes · US women's", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Size guide" })).toBeVisible();
    await expect(page.getByText("Dress shirts", { exact: true })).toHaveCount(0);
    await page.getByRole("radio", { name: "Plus" }).click();
    // a group with sizes picked starts folded, showing the picks; open it
    await page.locator("details", { hasText: "Tops & dresses" }).evaluate((d) => ((d as HTMLDetailsElement).open = true));
    await expect(page.getByRole("button", { name: "1X", exact: true })).toBeVisible();
    await page.getByRole("radio", { name: "Regular" }).click();
    await expect(page.getByRole("heading", { name: "Your area" })).toBeVisible();
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
    // Men shows the men's groups instead (not saved)
    await page.getByRole("button", { name: "Men", exact: true }).click();
    await expect(page.getByText("Dress shirts", { exact: true })).toBeVisible();
    await expect(page.getByText("Tops & dresses", { exact: true })).toHaveCount(0);
    await noHorizontalScroll(page);
  });

  test("closet item detail shows the outfit as one set of picture cards (B2, P8)", async ({ page }) => {
    await logIn(page);
    await page.goto("/closet");
    await page.getByRole("link", { name: "Grey pleated midi skirt" }).first().click();
    await expect(page.getByRole("heading", { name: "Finds that go with this" })).toBeVisible();
    await expect(page.getByText("Styled for you")).toBeVisible({ timeout: 120_000 });
    const cards = page.getByRole("list", { name: /^Your Grey pleated midi skirt with/ });
    await expect(cards).toBeVisible();
    const pieces = (await cards.locator(":scope > li").count()) - 1; // the first card is your own piece
    expect(pieces).toBeGreaterThanOrEqual(2);
    // every card has a picture, and each piece has either View on … (a listing) or Search this
    expect(await cards.locator(":scope > li img").count()).toBe(pieces + 1);
    const views = await cards.getByRole("link", { name: /^View on / }).count();
    const searches = await cards.getByRole("link", { name: "Search this" }).count();
    expect(views + searches).toBe(pieces);
    // no separate text-only piece list any more
    await expect(page.getByRole("group", { name: /Outfit collage/ })).toHaveCount(0);
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
