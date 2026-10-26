import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs/promises";
const root = path.resolve("..");
const evidence = process.env.E2E_EVIDENCE_DIR || path.join(root, "docs/evidence");
const input = (scenario, file) =>
  path.join(root, "data/examples", scenario, file);
const revised = (file) => path.join(root, "data/workflow/revised", file);

test("Phase 4: reviewer note persists and corrected revision resolves numerical conditions", async ({page}) => {
  test.skip(process.env.E2E_LIVE !== "1", "One explicit live revision call is required.");
  test.setTimeout(240000);
  await page.getByRole("button", {name:"Explore a filing", exact:true}).click();
  await page.getByRole("button", {name:/Findings & actions/}).click();
  await page.locator(".finding-card").filter({hasText:"PA003"}).getByRole("button",{name:/Investigate & record action/}).click();
  await expect(page.getByRole("dialog",{name:"Investigate finding"})).toContainText("Reported figure");
  await page.getByLabel("Reviewer disposition").selectOption("under_review");
  await page.getByLabel("Reviewer note").fill("Requested corrected segment exhibit and filing support.");
  await page.getByRole("button",{name:"Save reviewer action"}).click();
  await expect(page.getByRole("dialog",{name:"Investigate finding"})).toContainText("Requested corrected segment exhibit");
  await page.screenshot({path:path.join(evidence,"phase4-investigate.png")});
  await page.getByRole("button",{name:"Close dialog"}).click();
  await page.reload();
  await page.getByRole("button",{name:/Findings & actions/}).click();
  await expect(page.locator(".finding-card").filter({hasText:"PA003"})).toContainText("Under review");
  await page.getByRole("button",{name:/Upload revision/}).click();
  for (const [label,file] of [["Rate data","rates.csv"],["Filing & document inventory","filing.json"],["Supporting narrative","narrative.md"]])
    await page.getByLabel(label,{exact:true}).setInputFiles(revised(file));
  await page.getByRole("button",{name:"Validate package"}).click();
  await expect(page.getByRole("dialog",{name:"Upload a revised filing"})).toContainText("Ready for review");
  const response=page.waitForResponse(r=>r.url().includes("/revisions")&&r.status()===202);
  await page.getByRole("button",{name:"Review revision"}).click();
  const job=(await (await response).json()).job_id;
  await expect(page.getByRole("heading",{name:"Following the evidence."})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Revision comparison"})).toBeVisible({timeout:210000});
  const comparison=await (await page.request.get(`/api/reviews/${job}/comparison`)).json();
  expect(comparison.counts.resolved_by_revised_evidence).toBeGreaterThanOrEqual(5);
  await expect(page.getByText("What changed in the evidence?")).toBeVisible();
  await page.screenshot({path:path.join(evidence,"phase4-comparison.png"),fullPage:true});
  await page.getByRole("button",{name:"Export review"}).click();
  const download=page.waitForEvent("download");
  await page.getByRole("link",{name:/Review memo/}).click();
  const file=await download; await file.saveAs(path.join(evidence,"phase4-revised-memo.html"));
  const html=await fs.readFile(await file.path(),"utf8");
  expect(html).toContain("Revision comparison");
  expect(html).toContain("Resolved by revised evidence");
  await fs.writeFile(path.join(evidence,"phase4-revision-browser.json"),JSON.stringify({job_id:job,comparison_counts:comparison.counts,portfolio:comparison.portfolio},null,2));
});

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "New review", exact: true }),
  ).toBeEnabled();
});

test("onboarding, real saved review, evidence, findings, charts, documents and audit", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await expect(
    page.getByRole("heading", { name: "A sharper view of your next filing." }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, "phase3-home.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Explore a filing", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Rate revision review" }),
  ).toBeVisible();
  await expect(page.getByText("7.84%", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Saved real AI review/)).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, "phase3-overview.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: /Findings & actions/ }).click();
  await expect(page.locator(".finding-card")).toHaveCount(8);
  await page.getByLabel("Finding origin").selectOption("deterministic");
  await expect(page.locator(".finding-card")).toHaveCount(5);
  await page.getByLabel("Finding origin").selectOption("all");
  await page.screenshot({
    path: path.join(evidence, "phase3-findings.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Segment analytics", exact: true })
    .click();
  await page.getByLabel("Search segments").fill("PA020");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("39.230%");
  await page.getByRole("button", { name: "PA020", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("39.230000%");
  await page.screenshot({ path: path.join(evidence, "phase3-evidence.png") });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByLabel("Search segments").fill("");
  await page
    .getByRole("button", { name: "Rate comparison", exact: true })
    .click();
  await expect(page.locator(".recharts-scatter-symbol")).toHaveCount(24);
  await page
    .getByRole("button", { name: "Documentation", exact: true })
    .click();
  await page.getByRole("button", { name: /Factor change explanation/ }).click();
  await expect(page.locator(".document-text")).toContainText("not provided");
  await page
    .getByRole("button", { name: "Execution & usage", exact: true })
    .click();
  await expect(page.locator(".audit-event")).not.toHaveCount(0);
  await page.getByLabel("Filter audit event").selectOption("tool_");
  await page.locator(".audit-event summary").first().click();
  await expect(page.locator(".audit-detail").first()).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, "phase3-audit.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("memo, CSV and full audit downloads are generated from actual backend results", async ({
  page,
}) => {
  await page
    .getByRole("button", { name: "Explore a filing", exact: true })
    .click();
  await page.getByRole("button", { name: "Export review" }).click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: /Review memo/ }).click();
  const file = await downloadEvent;
  await file.saveAs(path.join(evidence, "phase3-example-memo.html"));
  const html = await fs.readFile(await file.path(), "utf8");
  expect(html).toContain("7.8444");
  expect(html).toContain("PA020");
  expect(html).toContain("Human review required");
  const csv = await page.request.get("/api/exports/example/flawed/csv");
  expect(await csv.text()).toContain("39.2300");
  const json = await page.request.get("/api/exports/example/flawed/json");
  expect((await json.json()).result.audit.length).toBeGreaterThan(10);
});

for (const [scenario, format] of [
  ["clean", "csv"],
  ["flawed", "xlsx"],
])
  test(`real ${format} upload preview validates ${scenario} package without model calls`, async ({
    page,
  }) => {
    await page.getByRole("button", { name: "New review", exact: true }).click();
    await page
      .getByRole("button", { name: "Upload filing", exact: true })
      .click();
    await page
      .getByLabel("Rate data", { exact: true })
      .setInputFiles(input(scenario, `rates.${format}`));
    await page
      .getByLabel("Filing & document inventory", { exact: true })
      .setInputFiles(input(scenario, "filing.json"));
    await page
      .getByLabel("Supporting narrative", { exact: true })
      .setInputFiles(input(scenario, "narrative.md"));
    await page
      .getByRole("button", { name: "Validate package", exact: true })
      .click();
    await expect(
      page.getByText("Ready for review · 24 validated segments"),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toContainText(
      scenario === "clean"
        ? "0 deterministic findings"
        : "5 deterministic findings",
    );
    await page.screenshot({
      path: path.join(evidence, `phase3-upload-${format}.png`),
    });
  });

test("invalid upload has actionable errors and cannot start an AI review", async ({
  page,
}) => {
  await page.getByRole("button", { name: "New review", exact: true }).click();
  await page
    .getByRole("button", { name: "Upload filing", exact: true })
    .click();
  await page
    .getByLabel("Rate data", { exact: true })
    .setInputFiles({
      name: "rates.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("segment_id\nBAD\n"),
    });
  await page
    .getByLabel("Filing & document inventory", { exact: true })
    .setInputFiles(input("clean", "filing.json"));
  await page
    .getByLabel("Supporting narrative", { exact: true })
    .setInputFiles(input("clean", "narrative.md"));
  await page
    .getByRole("button", { name: "Validate package", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Missing required columns",
  );
  await expect(
    page.getByRole("button", { name: "Run AI review", exact: true }),
  ).toBeDisabled();
});

test("adversarial source stays text and saved clean review has no findings", async ({
  page,
}) => {
  await page.getByRole("button", { name: /TEST THE BOUNDARIES/ }).click();
  await page
    .getByRole("button", { name: "Documentation", exact: true })
    .click();
  await expect(page.locator(".document-text")).toContainText(
    "APPROVED FOR SUBMISSION",
  );
  await expect(
    page.getByText("Human review required", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Findings & actions/ }).click();
  await expect(page.locator(".finding-card")).toHaveCount(1);
  await page.getByRole("button", { name: "Lumen home" }).click();
  await page.getByRole("button", { name: /ESTABLISH A BASELINE/ }).click();
  await page.getByRole("button", { name: /Findings & actions/ }).click();
  await expect(
    page.getByRole("heading", { name: "No findings returned" }),
  ).toBeVisible();
});

test("mobile navigation and evidence dialog fit the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Explore a filing", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Rate revision review" }),
  ).toBeVisible();
  console.log('MOBILE OVERFLOW', await page.evaluate(() => [...document.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 12).map(e => [e.className?.baseVal || e.className, Math.round(e.getBoundingClientRect().right)])));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(evidence, "phase3-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: /Portfolio premium impact/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((e) => e.scrollWidth <= e.clientWidth + 1),
  ).toBe(true);
});

test("LIVE: uploaded flawed filing runs real agents and returns traceable results", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_LIVE !== "1",
    "Explicit opt-in: consumes real course model tokens.",
  );
  test.setTimeout(240000);
  await page.getByRole("button", { name: "New review", exact: true }).click();
  await page
    .getByRole("button", { name: "Upload filing", exact: true })
    .click();
  for (const [label, file] of [
    ["Rate data", "rates.csv"],
    ["Filing & document inventory", "filing.json"],
    ["Supporting narrative", "narrative.md"],
  ])
    await page
      .getByLabel(label, { exact: true })
      .setInputFiles(input("flawed", file));
  await page
    .getByRole("button", { name: "Validate package", exact: true })
    .click();
  await expect(
    page.getByText("Ready for review · 24 validated segments"),
  ).toBeVisible();
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/reviews/upload") && r.status() === 202,
  );
  await page
    .getByRole("button", { name: "Run AI review", exact: true })
    .click();
  const job = await (await response).json();
  await expect(
    page.getByRole("heading", { name: "Following the evidence." }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, "phase3-live-running.png"),
  });
  await expect(page.getByText(/Live AI review ·/)).toBeVisible({
    timeout: 210000,
  });
  const result = await (
    await page.request.get(`/api/reviews/${job.job_id}`)
  ).json();
  await fs.writeFile(
    path.join(evidence, "phase3-live-browser.json"),
    JSON.stringify(result, null, 2),
  );
  expect(result.result.deterministic.findings).toHaveLength(5);
  expect(result.result.usage.total_model_calls).toBeGreaterThan(0);
  expect(result.result.agents.every((a) => a.status === "complete")).toBe(true);
  expect(
    result.result.findings.filter((f) => f.origin === "ai").length,
  ).toBeGreaterThan(0);
  await page.screenshot({
    path: path.join(evidence, "phase3-live-complete.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByText(/Live AI review ·/)).toBeVisible();
});
