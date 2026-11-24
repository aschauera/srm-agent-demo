import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { Script } from "node:vm";
import { build } from "esbuild";
import { Window } from "happy-dom";

const mockSdk = `
export class App {
  constructor() { globalThis.testApp = this; }
  connect() { return Promise.resolve(); }
  getHostContext() { return { theme: "light" }; }
  callServerTool(args) { this.lastCall = args; return Promise.resolve(this.nextResult); }
  openLink() { return Promise.resolve({}); }
}`;
const bundle = await build({
  entryPoints: ["app.ts"], bundle: true, format: "iife", write: false,
  plugins: [{
    name: "test-host",
    setup(builder) {
      builder.onResolve({ filter: /^@modelcontextprotocol\/ext-apps$/ }, () => ({ path: "sdk", namespace: "test" }));
      builder.onLoad({ filter: /.*/, namespace: "test" }, () => ({ contents: mockSdk, loader: "js" }));
    },
  }],
});
const html = await readFile("index.html", "utf8");
const data = {
  supplier: { code: "SUP-012", name: "Lumen Forge Industrial Systems Ltd", country: "United States",
    division: "Powertrain", category: "Precision machining", duns: "900000012", annualSpend: 12700000, masterRating: "Red" },
  review: { ref: "REQ-2026-012", status: "In Progress", path: "Full Review", stage: 3,
    stageName: "Analysis & Rating", preliminaryRating: "Green", finalRating: "Not rated", confirmed: false,
    expired: false, ratingDate: null, ratingExpiry: null, overridden: false, narrativeDraft: null,
    officialCommentary: null, modifiedOn: "2026-11-03T09:45:50Z" },
  coface: { score: 2, tier: "High", assessmentDate: "2024-08-19", current: false, creditLimit: 450000, reportUrl: null },
  financials: [2023, 2024, 2025, 2026].map((year, i) => ({
    year, period: year === 2026 ? "Interim" : "Full year", currency: "USD",
    revenue: [100000000, 95000000, 88000000, 35000000][i],
    netIncome: null, cashFlow: null, leverage: null, liquidity: null, grossMargin: null,
  })),
  ratingHistory: [], profile: null, sourceAttribution: null, trendInterpretation: null,
  summaryGeneratedOn: null, summaryVersion: null, adverseEvents: [], nonFinancialRisks: [],
  sensitiveVisible: false, warnings: ["Human final-rating decision pending."],
  fetchedAt: "2026-11-23T15:00:00Z", source: "Fictional test data",
};

test("the self-contained production HTML contains executable, uncorrupted scripts", async () => {
  const artifact = await readFile("../dist/dashboard.html", "utf8");
  const scripts = [...artifact.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  assert.equal(scripts.length, 2, "Bundling must not inject duplicate HTML or script blocks.");
  assert.ok(!artifact.includes("/* MCP_APP_BUNDLE */"), "The bundle marker must be replaced exactly once.");
  for (const [index, script] of scripts.entries()) {
    assert.doesNotThrow(() => new Script(script[1], { filename: `dashboard-script-${index}.js` }));
  }
});

test("the production SDK initializes and renders a host-delivered tool result", async () => {
  const artifact = await readFile("../dist/dashboard.html", "utf8");
  const scripts = [...artifact.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  const window = new Window({ url: "http://localhost/", settings: { enableJavaScriptEvaluation: true } });
  const messages = [];
  let markInitialized;
  const initialized = new Promise(resolve => { markInitialized = resolve; });
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("The bundled SDK did not initialize.")), 1000);
  });
  function deliver(message) {
    window.hostMessage = message;
    window.eval('window.dispatchEvent(new MessageEvent("message", { source: window.parent, data: window.hostMessage }))');
  }
  window.document.write(artifact.replace(/<script>[\s\S]*?<\/script>/g, ""));
  window.postMessage = message => {
    messages.push(message);
    if (message.method === "ui/initialize") {
      setTimeout(() => deliver({
        jsonrpc: "2.0", id: message.id, result: {
          protocolVersion: "2026-01-26",
          hostInfo: { name: "test-host", version: "1.0.0" },
          hostCapabilities: {}, hostContext: { theme: "dark" },
        },
      }), 0);
    }
    if (message.method === "ui/notifications/initialized") markInitialized();
  };
  try {
    for (const script of scripts) window.eval(script[1]);
    await Promise.race([initialized, timeout]);
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.ok(messages.some(message => message.method === "ui/notifications/initialized"),
      "The actual bundled SDK must finish its initialization handshake.");
    deliver({
      jsonrpc: "2.0", method: "ui/notifications/tool-result",
      params: { content: [], structuredContent: data },
    });
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(window.document.getElementById("supplier-name").textContent, data.supplier.name);
    assert.equal(window.document.getElementById("dashboard").hidden, false);
    assert.equal(window.document.documentElement.dataset.theme, "dark");
  } finally { clearTimeout(timer); window.happyDOM.abort(); }
});

async function setup(query = "") {
  const window = new Window({ url: `http://localhost/${query}`, settings: { enableJavaScriptEvaluation: true } });
  window.matchMedia = () => ({ matches: true, addEventListener() {} });
  window.document.write(html.replace(/<script>[\s\S]*?<\/script>/g, ""));
  window.eval(bundle.outputFiles[0].text);
  await new Promise(resolve => setTimeout(resolve, 0));
  return { window, document: window.document, app: window.testApp };
}

test("master traffic light does not turn the AI draft into human approval", async () => {
  const { window, document, app } = await setup();
  try {
    app.ontoolresult({ structuredContent: data });
    assert.equal(document.getElementById("master-rating").textContent, "Red");
    assert.equal(document.getElementById("ai-rating").textContent, "Green");
    assert.equal(document.getElementById("final-rating").textContent, "Decision pending");
    assert.equal(document.querySelectorAll(".lamp.red.active").length, 1);
    assert.equal(document.querySelectorAll(".lamp.green.active").length, 0);
    assert.match(document.getElementById("coface-tier").textContent, /Historical - not current/);
    assert.match(document.getElementById("commentary").textContent, /LegalReader/);
    assert.equal(document.querySelectorAll("#financials tr").length, 4);
    assert.equal(document.querySelectorAll("#revenue-chart circle").length, 3);
  } finally { window.happyDOM.abort(); }
});

test("host theme changes override the URL and operating-system preference", async () => {
  const { window, document, app } = await setup("?scoutTheme=light");
  try {
    assert.equal(document.documentElement.dataset.theme, "light");
    const light = window.getComputedStyle(document.body).backgroundColor;
    app.onhostcontextchanged({ theme: "dark" });
    assert.equal(document.documentElement.dataset.theme, "dark");
    assert.notEqual(window.getComputedStyle(document.body).backgroundColor, light);
    app.onhostcontextchanged({ theme: "light" });
    assert.equal(document.documentElement.dataset.theme, "light");
  } finally { window.happyDOM.abort(); }
});

test("refresh uses the exact supplier/request and hides stale data on failure", async () => {
  const { window, document, app } = await setup();
  try {
    app.ontoolresult({ structuredContent: { ...data, supplier: { ...data.supplier, name: "<img src=x onerror=alert(1)>" } } });
    assert.equal(document.querySelectorAll("img").length, 0);
    assert.match(document.getElementById("supplier-name").textContent, /<img/);
    app.nextResult = { isError: true };
    document.getElementById("refresh").click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(app.lastCall.arguments.supplier_code, "SUP-012");
    assert.equal(app.lastCall.arguments.request_ref, "REQ-2026-012");
    assert.equal(document.getElementById("dashboard").hidden, true);
    assert.equal(document.getElementById("error").hidden, false);
    assert.equal(document.getElementById("refresh").disabled, false);
  } finally { window.happyDOM.abort(); }
});
