import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const EMAIL = process.env.TEST_USER_EMAIL;
const PASSWORD = process.env.TEST_USER_PASSWORD;
const PHOTO = path.join(__dirname, "..", "..", "backend", "tests", "closet_photos", "a29c70492f84c2b51cd7a26151409efc.jpg");

async function noHorizontalScroll(page: Page) {
  const { scroll, width } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: window.innerWidth,
  }));
  expect(scroll, `page is ${scroll}px wide in a ${width}px window`).toBeLessThanOrEqual(width);
}

const isDesktop = (page: Page) => (page.viewportSize()?.width || 0) >= 768;

async function logIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL!);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD!);
  await page.getByRole("button", { name: "Log in" }).click();
  await page.waitForURL(/\/(home|onboarding)/);
}

test.describe("guest", () => {
  test("landing page", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Find pieces that fit your wardrobe, not just your search.",
    );
    await expect(page.getByText("5 stores live:")).toBeVisible();
    await expect(page.getByText("FB Marketplace (coming soon)")).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("legal pages show the draft banner", async ({ page }) => {
    for (const p of ["/terms", "/privacy"]) {
      await page.goto(p);
      await expect(page.getByRole("note")).toContainText("DRAFT");
      await noHorizontalScroll(page);
    }
  });

  test("sign-up needs the terms box and a 12-character password", async ({ page }) => {
    await page.goto("/signup");
    await page.getByLabel("Email", { exact: true }).fill("someone@example.com");
    await page.getByLabel("Password", { exact: true }).fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Use at least 12 characters")).toBeVisible();
    await expect(page.getByText("Please agree to the Terms of Service")).toBeVisible();
    await expect(page).toHaveURL(/\/signup/);
    await noHorizontalScroll(page);
  });

  test("guest search shows a styled best match", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("searchbox", { name: "Try a search" }).fill("vintage graphic tee under $30");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page).toHaveURL(/\/search\?q=/);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: "Remove filter under $30" })).toBeVisible();
    await expect(page.getByRole("link", { name: /^View on / })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign up" }).first()).toBeVisible();
    if (isDesktop(page)) {
      const stores = page.getByRole("group", { name: /Stores/ });
      await expect(stores.getByText("coming soon").first()).toBeVisible();
      await expect(stores.getByRole("checkbox", { name: /FB Marketplace/ })).toBeDisabled();
    } else {
      await expect(page.getByText("FB Marketplace · coming soon")).toBeVisible();
    }
    // every price shown is within the budget
    const prices = await page.locator("article").getByText(/^\$\d+(\.\d+)?$/).allInnerTexts();
    expect(prices.length).toBeGreaterThan(0);
    for (const p of prices) expect(Number(p.slice(1))).toBeLessThanOrEqual(30);
    await noHorizontalScroll(page);
  });

  test("empty search relaxes the size itself, then offers a bigger budget", async ({ page }) => {
    await page.goto(`/search?q=${encodeURIComponent("designer ballgown size XXS under $5")}`);
    // fixtures mode (tests): the empty state says the recorded data doesn't cover this search
    await expect(page.getByText("Development data doesn't include this search")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Nothing matched in size XXS, so I searched every size.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Raise budget to $10" })).toBeVisible();
    await page.getByRole("button", { name: "Raise budget to $10" }).click();
    await expect(page).toHaveURL(/max=10/);
    await noHorizontalScroll(page);
  });

  test("signed-in pages send guests to log in", async ({ page }) => {
    await page.goto("/closet");
    await expect(page).toHaveURL(/\/login\?next=%2Fcloset/);
  });
});

test.describe("signed in (test account)", () => {
  test.skip(!EMAIL || !PASSWORD, "TEST_USER_EMAIL / TEST_USER_PASSWORD not set");

  test("home, closet, item detail, saved, profile", async ({ page }) => {
    await logIn(page);
    await page.goto("/home");
    await expect(page.getByRole("heading", { name: "Picked for your closet" })).toBeVisible();
    await expect(page.getByText(/Goes with your|Picks up the/).first()).toBeVisible();
    await noHorizontalScroll(page);

    await page.getByRole("button", { name: "Search by photo — coming soon" }).first().click();
    await expect(page.getByRole("dialog")).toContainText("Coming soon");
    await page.getByRole("button", { name: "Got it" }).click();

    const nav = page.getByRole("navigation", { name: "Main" });
    await nav.getByRole("link", { name: "Closet" }).click();
    await expect(page.getByRole("heading", { name: "My Closet" })).toBeVisible();
    await expect(page.getByText(/\d+ items · only you can see this/)).toBeVisible();
    if (isDesktop(page)) await expect(page.getByRole("heading", { name: "Categories" })).toBeVisible();
    await noHorizontalScroll(page);

    await page.getByRole("link", { name: "Black leather jacket" }).first().click();
    await expect(page.getByRole("heading", { name: "Black leather jacket" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Finds that go with this" })).toBeVisible();
    await noHorizontalScroll(page);

    await nav.getByRole("link", { name: "Saved" }).click();
    await expect(page.getByRole("heading", { name: "Saved", level: 1 })).toBeVisible();
    await noHorizontalScroll(page);

    await nav.getByRole("link", { name: "Profile" }).click();
    await expect(page.getByRole("heading", { name: "Your sizes and style" })).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("search styles the find with the user's own closet", async ({ page }) => {
    await logIn(page);
    await page.goto(`/search?q=${encodeURIComponent("flannel shirt")}`);
    await expect(page.getByText("Best match", { exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "How to wear it with your closet" })).toBeVisible();
    // profile filters appear as removable "from profile" chips
    await expect(page.getByRole("button", { name: /from your profile/ }).first()).toBeVisible();
    await noHorizontalScroll(page);
  });

  test("add an item with a photo, then delete it", async ({ page }) => {
    await logIn(page);
    await page.goto("/closet/new");
    await expect(page.getByRole("heading", { name: "Add item" })).toBeVisible();

    // unsupported file is refused with a reason
    await page.getByLabel("Choose a photo from your library").setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("not a photo"),
    });
    await expect(page.getByText("That file type isn't supported. Use a JPG, PNG or HEIC photo.")).toBeVisible();

    await page.getByLabel("Choose a photo from your library").setInputFiles(PHOTO);
    await expect(page.getByRole("img", { name: "Your photo of the item" })).toBeVisible();
    // auto-tagging (A3) runs first; wait for it so it can't overwrite what we type
    await expect(page.getByText("Reading your photo")).toHaveCount(0, { timeout: 60_000 });
    await page.getByLabel("Name").fill("E2E test jacket");
    await page.getByRole("button", { name: "Outerwear" }).click();
    const black = page.getByRole("button", { name: "black", exact: true });
    if ((await black.getAttribute("aria-pressed")) !== "true") await black.click();
    await noHorizontalScroll(page);
    await page.getByRole("button", { name: "Save to closet" }).click();

    await expect(page.getByRole("heading", { name: "E2E test jacket" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Saved to your closet.")).toBeVisible();
    await page.getByRole("button", { name: "Delete item" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
    await expect(page).toHaveURL(/\/closet$/);
    await expect(page.getByRole("link", { name: "E2E test jacket" })).toHaveCount(0);
  });
});
