// Run after building _site. Requires Playwright and an installed Chrome browser.
// Serve local artifacts at the production origin inside an isolated browser.
// Intercept Analytics collection so test visits never reach the real property.
import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { extname, resolve, sep } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || "playwright");
const root = resolve(process.argv[2] || "_site");
const origin = "https://codefortoyama.github.io";
const output = resolve(tmpdir(), "codefortoyama-browser-security");
mkdirSync(output, { recursive: true });
const types = { ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".png": "image/png", ".ico": "image/x-icon" };
const isCollection = (url) => {
  const parsed = new URL(url);
  return /(^|\.)(google-analytics\.com|google\.com|googletagmanager\.com)$/.test(parsed.hostname)
    && parsed.pathname.includes("collect");
};
const browser = await chromium.launch({ channel: "chrome", headless: true, timeout: 30000 });
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript(() => {
    window.cspViolations = [];
    document.addEventListener("securitypolicyviolation", (event) => {
      window.cspViolations.push({ directive: event.effectiveDirective, blocked: event.blockedURI });
    });
  });
  const collections = [];
  const unexpectedRequests = [];
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (isCollection(url.href)) {
      collections.push(url.href);
      return route.fulfill({ status: 204, headers: { "Access-Control-Allow-Origin": origin } });
    }
    if (url.origin === origin) {
      const file = resolve(root, "." + decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname));
      assert.ok(file.startsWith(root + sep), "Artifact path must stay inside _site");
      if (existsSync(file)) return route.fulfill({ body: readFileSync(file), contentType: types[extname(file)] || "application/octet-stream" });
      // Published project images share the site's origin but live in other repositories.
      if (route.request().resourceType() === "image") return route.continue();
      return route.fulfill({ status: 404, body: "Not found in local artifact" });
    }
    if ((url.hostname === "www.googletagmanager.com" && url.pathname === "/gtag/js")
        || (url.hostname === "media.connpass.com" && route.request().resourceType() === "image")) {
      return route.continue();
    }
    unexpectedRequests.push(url.href);
    return route.abort();
  });

  for (const path of ["/", "/projects.html", "/privacy.html"]) {
    const page = await context.newPage();
    const errors = [];
    const consoleErrors = [];
    const failedRequests = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
    page.on("requestfailed", (request) => failedRequests.push({ url: request.url(), reason: request.failure()?.errorText }));
    const collected = page.waitForRequest((request) => isCollection(request.url()), { timeout: 20000 });
    collected.catch(() => {});
    await page.goto(origin + path, { waitUntil: "load" });
    let collectionRequest;
    try {
      collectionRequest = await collected;
    } catch (error) {
      console.error(JSON.stringify({ page: path, errors, consoleErrors, failedRequests, violations: await page.evaluate(() => window.cspViolations) }));
      throw error;
    }
    assert.equal(collectionRequest.headers().referer, origin + "/", "Cross-origin Analytics request must omit the page path");
    await page.locator(".menu-toggle").click();
    assert.equal(await page.locator(".menu-toggle").getAttribute("aria-expanded"), "true");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator(".menu-toggle").getAttribute("aria-expanded"), "false");
    await page.locator("details").evaluateAll((details) => details.forEach((item) => { item.open = true; }));
    for (const image of await page.locator("img").all()) {
      if (await image.isVisible()) await image.scrollIntoViewIfNeeded();
    }
    try {
      await page.waitForFunction(() => [...document.images].every((image) => image.getClientRects().length === 0 || (image.complete && image.naturalWidth > 0)));
    } catch (error) {
      console.error(JSON.stringify({ page: path, images: await page.locator("img").evaluateAll((images) => images.map((image) => ({ src: image.src, complete: image.complete, width: image.naturalWidth }))), failedRequests, violations: await page.evaluate(() => window.cspViolations) }));
      throw error;
    }
    assert.deepEqual(errors, [], "Normal page must have no JavaScript errors");
    assert.deepEqual(await page.evaluate(() => window.cspViolations), [], "Normal page must have no CSP violations");

    // Inject actual DOM script elements; evaluate itself bypasses page CSP.
    await page.evaluate(() => {
      const inline = document.createElement("script");
      inline.textContent = "window.injectedInline = true";
      document.body.append(inline);
      const external = document.createElement("script");
      external.src = "https://untrusted.example/injected.js";
      document.body.append(external);
      const googleOtherPath = document.createElement("script");
      googleOtherPath.src = "https://www.googletagmanager.com/untrusted.js";
      document.body.append(googleOtherPath);
    });
    await page.waitForFunction(() => window.cspViolations.length >= 3);
    assert.equal(await page.evaluate(() => window.injectedInline), undefined);
    assert.ok((await page.evaluate(() => window.cspViolations)).every((violation) => violation.directive === "script-src-elem"));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: resolve(output, path === "/" ? "index.png" : path.slice(1) + ".png") });
    await page.setViewportSize({ width: 1280, height: 900 });
    assert.equal(await page.locator("#navigation a").first().isVisible(), true);
    console.log(JSON.stringify({ page: path, mobileMenu: "passed", images: "passed", analytics: "intercepted collection request", blockedScripts: 3 }));
    await page.close();
  }

  // A failed external image must use the existing local fallback.
  await context.route("https://media.connpass.com/**", (route) => route.fulfill({ status: 404, body: "Simulated missing image" }));
  const fallbackPage = await context.newPage();
  await fallbackPage.goto(origin + "/", { waitUntil: "load" });
  const fallback = fallbackPage.locator(".event-eyecatch").first();
  await fallback.waitFor();
  await fallbackPage.waitForFunction(() => {
    const image = document.querySelector(".event-eyecatch");
    return image.src.endsWith("/assets/event-placeholder.svg") && image.complete && image.naturalWidth > 0;
  });
  assert.equal(await fallback.evaluate((image) => image.naturalWidth > 0), true);
  assert.deepEqual(unexpectedRequests, [], "CSP must block untrusted scripts before network access");
  console.log(JSON.stringify({ imageFallback: "passed", collectionsIntercepted: collections.length, screenshots: output }));
  await context.close();
} finally {
  await browser.close();
}
