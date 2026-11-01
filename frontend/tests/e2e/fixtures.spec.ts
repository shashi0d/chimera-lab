import { expect, test } from "@playwright/test";
import { addPhotos, log, make, openApp, openLab, trace, typeNames, waitFinished } from "./helpers";

// One test per contract fixture (docs/api_fixtures/*.json), driven through the UI against the mock transport.

test("gallery: the six showcase creatures, each labelled Generated fusion, open their card", async ({ page }) => {
  await openApp(page);
  await expect(page.getByRole("heading", { level: 1, name: "Creatures made by an agent" })).toBeVisible();
  const cards = page.locator(".gcard__link");
  await expect(cards).toHaveCount(6);
  for (let i = 0; i < 6; i++) await expect(cards.nth(i).getByText("Generated fusion")).toBeVisible();
  await expect(cards.first()).toContainText("Indian pangolin × horse");
  await cards.first().click();
  await expect(page).toHaveURL(/\?creature=crt_fx_b09$/);
  await expect(page.getByRole("heading", { level: 1, name: "Indian pangolin × horse" })).toBeVisible();
  await page.goBack();
  await expect(cards).toHaveCount(6);
});

test("limits: open shows the runs left; capped shows the cap before any upload and disables the action", async ({ page }) => {
  await openApp(page);
  await expect(page.getByText(/38 of 50 live runs left today; you can start 2 more/)).toBeVisible();
  await openApp(page, "/", { scenario: "limits_capped" });
  await expect(page.getByText("Today's live creature runs are used up.")).toBeVisible();
  await expect(page.getByText(/new runs open again at 00:00 UTC/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Make a new creature" })).toBeDisabled();
  await expect(page.locator(".gcard__link")).toHaveCount(6); // the gallery still works
  await page.goto("/?view=lab");
  await typeNames(page, "lion", "tiger");
  await expect(page.locator(".fusion-node__make")).toBeDisabled();
  await expect(page.locator(".node--fusion")).toContainText("Today's live runs are used up");
});

test("creature_b09: image, host with reason, Can it live, anatomy overlay on and off with the legend", async ({ page }) => {
  await openApp(page, "/?creature=crt_fx_b09");
  await expect(page.getByText("Host: horse.")).toBeVisible();
  await expect(page.getByText("6 of 6 life functions work; no fiction licenses")).toBeVisible();
  const img = page.locator(".creature__img");
  await expect(img).toHaveAttribute("src", /b09_img2\.jpg$/);
  const toggle = page.getByRole("button", { name: "Anatomy map" });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await expect(img).toHaveAttribute("src", /b09_anatomy\.jpg$/);
  await expect(page.getByLabel("Anatomy map legend")).toContainText("Host");
  await expect(page.getByLabel("Anatomy map legend")).toContainText("Not located in the image: indian pangolin covering");
  await toggle.click();
  await expect(img).toHaveAttribute("src", /b09_img2\.jpg$/);
  await expect(page.locator(".creature__img")).toHaveJSProperty("complete", true);
});

test("run_success: steps stream in with reasons, the creature lands on the canvas and its card opens", async ({ page }) => {
  await openLab(page, { scenario: "success", stepMs: 150 });
  await typeNames(page, "Indian pangolin", "horse");
  await make(page);
  await expect(page).toHaveURL(/\?run=run_fx_success-/);
  await expect(trace(page)).toBeVisible();
  await expect(page.getByText("A creature takes about 5 minutes.").first()).toBeVisible();
  await expect(log(page).getByText("Chose a body plan")).toBeVisible();
  await expect(log(page).getByText(/Chosen horse as host for realistic mode/)).toBeVisible();
  await waitFinished(page);
  await expect(page.locator(".result-sum")).toContainText("Host: horse.");
  await expect(page.locator(".node--result")).toContainText("Indian pangolin × horse");
  await expect(page.locator(".node--result")).toContainText("Generated fusion");
  await page.locator(".result-sum").getByRole("button", { name: "Open creature card" }).click();
  await expect(page).toHaveURL(/\?creature=crt_fx_b09$/);
});

test("run_host_tie: the agent asks; the answer is posted and the run finishes with the chosen host", async ({ page }) => {
  await openLab(page, { scenario: "host_tie", stepMs: 100 });
  await typeNames(page, "tortoise", "domestic goat");
  await make(page);
  const choice = page.locator(".choice");
  await expect(choice.getByRole("heading", { name: "Both animals can carry the body. Which should be the host?" })).toBeVisible();
  await expect(page.locator(".node--fusion")).toContainText("Needs your choice");
  await expect(choice).toContainText(/the agent decides itself/);
  await choice.getByRole("button", { name: "domestic goat" }).click();
  await expect(log(page).getByText("You chose domestic goat.")).toBeVisible();
  await waitFinished(page);
  await expect(page.locator(".result-sum")).toContainText("Host: domestic goat. You chose it.");
  await expect(page.locator(".result-sum")).toContainText("3 checks hidden until reviewed.");
});

test("identify_choice: the POST asks which animal; confirming starts the run with names only", async ({ page }) => {
  await openLab(page, { scenario: "identify_choice", stepMs: 80 });
  await addPhotos(page, ["lion", "horse"]);
  await make(page);
  const dialog = page.getByRole("dialog", { name: "Which animal is in the first photo?" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("54% sure");
  await dialog.getByRole("radio", { name: /Galápagos tortoise/ }).check();
  await dialog.getByRole("button", { name: "Use this animal" }).click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/\?run=run_fx_host_tie-/);
  await expect(page.locator(".choice")).toBeVisible();
});

test("identify_choice: cancel leaves nothing started", async ({ page }) => {
  await openLab(page, { scenario: "identify_choice" });
  await addPhotos(page, ["lion", "horse"]);
  await make(page);
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/view=lab/);
  await expect(page.locator(".fusion-node__make")).toBeEnabled();
});

test("run_cap: the render cap is a notice, not the end; the run finalizes its best image", async ({ page }) => {
  await openLab(page, { scenario: "cap", stepMs: 80 });
  await typeNames(page, "common octopus", "horse");
  await make(page);
  await expect(log(page).getByText(/Render limit reached \(4\)/)).toBeVisible({ timeout: 20_000 });
  await waitFinished(page);
  await expect(page.locator(".result-sum")).toContainText("1 check still failing.");
});

test("run_queued: the queue position shows (2, then 1), then the run starts and finishes", async ({ page }) => {
  await openLab(page, { scenario: "queued", stepMs: 700 });
  await typeNames(page, "lion", "golden eagle");
  await make(page);
  await expect(page.getByText("Position 2 in the queue")).toBeVisible();
  await expect(page.getByText("2 runs ahead of yours. It starts when a slot frees up.")).toBeVisible();
  await expect(page.locator(".node--fusion")).toContainText("Queued · #2");
  await expect(page.getByText("Position 1 in the queue")).toBeVisible();
  await expect(log(page).getByText(/Started: lion × golden eagle, mythic/)).toBeVisible();
  await waitFinished(page);
});

for (const [scenario, title] of [
  ["refused_human", "This looks like a photo of a person."],
  ["refused_type", "That file type isn't supported."],
  ["refused_size", "That image is too large."],
  ["refused_animal", "We couldn't find an animal in this image."],
  ["refused_corrupt", "That image is damaged and can't be read."],
] as const) {
  test(`upload_refused (${scenario}): the refusal is explained and the photo is flagged`, async ({ page }) => {
    await openLab(page, { scenario });
    await addPhotos(page, ["lion", "horse"]);
    await make(page);
    await expect(page.locator(".node--fusion [role=alert]")).toContainText(title);
    await expect(page.locator(".node--image-input.is-flagged")).toHaveCount(1);
    await expect(page.locator(".node--image-input").first()).toHaveClass(/is-flagged/);
    await expect(page).toHaveURL(/view=lab/);
  });
}

test("cap_daily: the POST is refused with 429 CAP_REACHED and the app switches to the capped state", async ({ page }) => {
  await openLab(page, { scenario: "cap_daily" });
  await typeNames(page, "lion", "tiger");
  await make(page);
  await expect(page.locator(".node--fusion [role=alert]")).toContainText("Today's live creature runs are used up.");
  await expect(page.locator(".fusion-node__make")).toBeDisabled();
  await page.getByRole("link", { name: "Gallery", exact: true }).click();
  await expect(page.getByRole("button", { name: "Make a new creature" })).toBeDisabled();
  await expect(page.getByText(/new runs open again at 00:00 UTC/)).toBeVisible();
});

test("run_error: the run fails mid-way; the trace says what happened and offers a retry", async ({ page }) => {
  await openLab(page, { scenario: "error", stepMs: 80 });
  await typeNames(page, "rhinoceros beetle", "brown bear");
  await make(page);
  await expect(page.locator(".trace").getByText("The image model stopped answering, so this run ended.")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".node--fusion")).toContainText("Failed");
  await expect(log(page).getByText("The run stopped with an error.")).toBeVisible();
  await expect(page.locator(".trace").getByRole("button", { name: "Try again" })).toBeVisible();
});

test("an unknown run id in the URL says it can't be found", async ({ page }) => {
  await openApp(page, "/?run=run_does_not_exist");
  await expect(page.getByText("This run can't be found.")).toBeVisible();
});

test("both picks: shown, agent's first, only when the agent and the code ranking disagree", async ({ page }) => {
  await openApp(page, "/?creature=crt_mock_b10_split");
  const picks = page.locator(".pick");
  await expect(picks).toHaveCount(2);
  await expect(picks.nth(0)).toContainText("Agent's pick");
  await expect(picks.nth(1)).toContainText("Code ranking's pick");
  await openApp(page, "/?creature=crt_fx_b10");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".pick")).toHaveCount(0);
});
