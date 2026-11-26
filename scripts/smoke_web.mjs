// Smoke test: open each route at each width in headless Chrome and report page errors.
// node scripts/smoke_web.mjs --base http://localhost:8600 [--routes /,/country?country=NGA] [--widths 1280,390]
//   [--shots dir] [--wait-text text] [--no-checks]
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ROUTES = ["/", "/country", "/compare", "/changes", "/video", "/regions", "/conflict", "/economy", "/hotspots",
  "/cases", "/explorer", "/stress", "/builder", "/data", "/introduction", "/guide", "/methodology", "/glossary", "/sources"];

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(`--${name}`); return i < 0 ? def : args[i + 1]; };
const base = opt("base", "http://localhost:8600").replace(/\/$/, "");
const routes = opt("routes", "") ? opt("routes").split(",") : ROUTES;
const widths = opt("widths", "1280,390").split(",").map(Number);
const shots = opt("shots", "");
const waitText = opt("wait-text", "");
const noChecks = args.includes("--no-checks");
const allowed = new Set(opt("allow-origins", "https://www.youtube-nocookie.com,https://www.youtube.com,https://i.ytimg.com").split(",").filter(Boolean));
// Built only by the scheduled refreshes, so a fresh checkout lacks them; the page shows that section's empty state.
const OPTIONAL = /^\/data\/(news\/[^/]+|videos|gdelt\/[^/]+)\.json$/;
const optional404 = (status, url) => status === 404 && OPTIONAL.test(new URL(url).pathname);
const maxWait = noChecks ? 40000 : 20000;
const idleMs = noChecks ? 1500 : 1000;

const CHROME = [process.env.CHROME, "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium",
  "/usr/bin/chromium-browser"].find((p) => p && existsSync(p));
if (!CHROME) { console.error("Chrome not found; set CHROME"); process.exit(2); }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const slug = (route) => route === "/" ? "home" : route.replace(/^\//, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/-$/, "");

const profile = mkdtempSync(join(tmpdir(), "smoke-"));
const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist", "about:blank"],
  { stdio: "ignore" });

async function connect() {
  for (let i = 0; i < 300; i++) {  // up to 30 s: Chrome starts slowly on a busy CI runner
    try {
      const v = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
      const ws = new WebSocket(v.webSocketDebuggerUrl);
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
      return ws;
    } catch { await sleep(100); }
  }
  throw new Error("could not reach Chrome");
}

const ws = await connect();
let nextId = 1;
const pending = new Map();
const listeners = new Set();
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id) { const p = pending.get(d.id); pending.delete(d.id); d.error ? p.rej(new Error(d.error.message)) : p.res(d.result); }
  else listeners.forEach((f) => f(d));
};
const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
  const id = nextId++;
  pending.set(id, { res, rej });
  ws.send(JSON.stringify({ id, method, params, sessionId }));
});

async function visit(route, width) {
  const url = base + route;
  const origin = new URL(base).origin;
  const { targetId } = await send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
  const S = (m, p) => send(m, p, sessionId);
  const errors = [];
  const urls = new Map();
  let inflight = 0, lastActivity = Date.now();
  const on = (d) => {
    if (d.sessionId !== sessionId) return;
    const p = d.params;
    switch (d.method) {
      case "Runtime.exceptionThrown":
        errors.push("exception: " + (p.exceptionDetails.exception?.description || p.exceptionDetails.text)); break;
      case "Runtime.consoleAPICalled":
        if (p.type === "error") errors.push("console.error: " + p.args.map((a) => a.value ?? a.description).join(" ")); break;
      case "Log.entryAdded": // network-sourced entries are covered by the request checks below
        if (p.entry.level === "error" && p.entry.source !== "network") errors.push("log: " + p.entry.text); break;
      case "Network.requestWillBeSent":
        if (!/^(data|blob|about):/.test(p.request.url)) {
          if (!urls.has(p.requestId)) inflight++; // a redirect hop reuses the requestId
          urls.set(p.requestId, p.request.url);
          const o = new URL(p.request.url).origin;
          if (o !== origin && !allowed.has(o) && p.type !== "Image") errors.push(`third-party ${p.type}: ${p.request.url}`);
        }
        lastActivity = Date.now(); break;
      case "Network.responseReceived":
        if (p.response.url.startsWith(origin) && p.response.status >= 400 && !p.response.url.endsWith("/favicon.ico")
          && !optional404(p.response.status, p.response.url)) errors.push(`HTTP ${p.response.status}: ${p.response.url}`);
        // An embedded cross-origin frame (the YouTube player) loads out of process: its loadingFinished never reaches this session.
        if (p.type === "Document" && !p.response.url.startsWith(origin) && urls.delete(p.requestId)) { inflight--; lastActivity = Date.now(); }
        // fetchJSON throws on a 404 without reading the body, so that request never finishes either.
        if (p.response.url.startsWith(origin) && optional404(p.response.status, p.response.url) && urls.delete(p.requestId)) { inflight--; lastActivity = Date.now(); }
        break;
      case "Network.loadingFinished":
        if (urls.delete(p.requestId)) inflight--;
        lastActivity = Date.now(); break;
      case "Network.loadingFailed": {
        const u = urls.get(p.requestId);
        if (urls.delete(p.requestId)) inflight--;
        if (u && u.startsWith(origin) && !p.canceled) errors.push(`request failed: ${u} (${p.errorText})`);
        lastActivity = Date.now(); break;
      }
    }
  };
  listeners.add(on);
  await Promise.all(["Runtime", "Log", "Network", "Page"].map((d) => S(`${d}.enable`)));
  await S("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
  await S("Page.navigate", { url });
  const ev = async (expr) => (await S("Runtime.evaluate", { expression: expr, returnByValue: true })).result.value;
  const t0 = Date.now();
  let busyUntil = 0, settled = false;
  while (Date.now() - t0 < maxWait) {
    await sleep(200);
    // Streamlit draws late: treat a skeleton or loading spinner as activity.
    const busy = await ev(`!!document.querySelector('[data-testid="stSkeleton"],[data-testid="stStatusWidget"],[data-testid="stSpinner"]')`).catch(() => true);
    if (busy) busyUntil = Date.now();
    const textOk = !waitText || await ev(`document.body && document.body.innerText.includes(${JSON.stringify(waitText)})`).catch(() => false);
    if (inflight <= 0 && Date.now() - Math.max(lastActivity, busyUntil) >= idleMs && textOk) { settled = true; break; }
  }
  const warnings = settled ? [] : [`timeout waiting for ${waitText && !(await ev(`document.body.innerText.includes(${JSON.stringify(waitText)})`).catch(() => false)) ? JSON.stringify(waitText) : "network idle"}`];
  const page = await ev(`({
    html: document.contentType === "text/html", // the API answers JSON: no <main>, no mobile viewport
    mainEmpty: !document.querySelector('main') || (!document.querySelector('main').children.length && !document.querySelector('main').textContent.trim()),
    drawError: document.body.innerText.includes("This page couldn't be drawn"),
    scrollWidth: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) })`);
  if (shots) {
    mkdirSync(shots, { recursive: true });
    const { cssContentSize: c } = await S("Page.getLayoutMetrics");
    const { data } = await S("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
      clip: { x: 0, y: 0, width, height: Math.min(Math.ceil(c.height), 16000), scale: 1 } });
    writeFileSync(join(shots, `${slug(route)}@${width}.png`), Buffer.from(data, "base64"));
  }
  if (noChecks) errors.length = 0; // checks do not apply to the Streamlit reference
  else {
    errors.push(...warnings);
    if (page.html && page.mainEmpty) errors.push("empty <main>");
    if (page.drawError) errors.push("page shows \"This page couldn't be drawn\"");
    if (page.html && page.scrollWidth > width) errors.push(`horizontal scroll: scrollWidth ${page.scrollWidth} > ${width}`);
  }
  listeners.delete(on);
  await send("Target.closeTarget", { targetId });
  if (noChecks && warnings.length) console.log(`warn ${route} @${width}: ${warnings[0]}`);
  return errors;
}

let failed = 0;
for (const route of routes) for (const width of widths) {
  const errors = await visit(route, width).catch((e) => ["harness: " + e.message]);
  const uniq = [...new Set(errors)];
  if (uniq.length) failed++;
  console.log(`${uniq.length ? "FAIL" : "ok  "} ${route} @${width}${uniq.map((e) => "\n     " + e).join("")}`);
}
console.log(`${routes.length * widths.length - failed}/${routes.length * widths.length} passed`);
ws.close();
chrome.kill();
await sleep(300);
try { rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(failed ? 1 : 0);
