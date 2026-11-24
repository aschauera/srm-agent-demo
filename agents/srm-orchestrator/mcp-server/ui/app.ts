import { App, type McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import { z } from "zod";

const nullableText = z.string().nullable();
const nullableNumber = z.number().nullable();
const rating = z.enum(["Green", "Yellow", "Red", "Not rated"]);
const schema = z.object({
  supplier: z.object({
    code: z.string(), name: z.string(), country: nullableText, division: nullableText,
    category: nullableText, duns: nullableText, annualSpend: nullableNumber, masterRating: rating,
  }),
  review: z.object({
    ref: z.string(), status: z.string(), path: z.string(), stage: z.number().int().min(1).max(5),
    stageName: z.string(), preliminaryRating: rating, finalRating: rating,
    confirmed: z.boolean(), expired: z.boolean(), ratingDate: nullableText, ratingExpiry: nullableText,
    overridden: z.boolean(), narrativeDraft: nullableText, officialCommentary: nullableText,
    modifiedOn: nullableText,
  }),
  coface: z.object({
    score: nullableNumber, tier: z.string(), assessmentDate: nullableText, current: z.boolean(),
    creditLimit: nullableNumber, reportUrl: nullableText,
  }),
  financials: z.array(z.object({
    year: nullableNumber, period: nullableText, currency: nullableText, revenue: nullableNumber,
    netIncome: nullableNumber, cashFlow: nullableNumber, leverage: nullableNumber,
    liquidity: nullableNumber, grossMargin: nullableNumber,
  })),
  ratingHistory: z.array(z.object({ ref: z.string(), date: nullableText, rating, cofaceScore: nullableNumber })),
  profile: nullableText, sourceAttribution: nullableText, trendInterpretation: nullableText,
  summaryGeneratedOn: nullableText, summaryVersion: nullableText,
  adverseEvents: z.array(z.object({
    headline: nullableText, severity: z.string(), date: nullableText, sourceUrl: nullableText,
  })),
  nonFinancialRisks: z.array(z.object({
    details: nullableText, severity: z.string(), date: nullableText, sourceUrl: nullableText,
  })),
  sensitiveVisible: z.boolean(), warnings: z.array(z.string()), fetchedAt: z.string(), source: z.string(),
});
type Dashboard = z.infer<typeof schema>;
type ToolResult = { isError?: boolean; structuredContent?: unknown; content?: unknown };

function el(id: string): HTMLElement {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing dashboard element: ${id}`);
  return node;
}

const app = new App({ name: "SRM Supplier Risk Dashboard", version: "1.0.0" });
let current: Dashboard | undefined;
let connected = false;
let refreshing = false;
let hostTheme: "light" | "dark" | undefined;
const media = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(context?: McpUiHostContext) {
  if (context?.theme === "light" || context?.theme === "dark") hostTheme = context.theme;
  const param = new URLSearchParams(location.search).get("scoutTheme");
  const theme = hostTheme ?? (param === "light" || param === "dark" ? param : media.matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
}
applyTheme();
media.addEventListener("change", () => applyTheme());
app.onhostcontextchanged = applyTheme;

function text(id: string, value: string) { el(id).textContent = value; }
function signal(value: string) {
  return ({ Red: "red", Yellow: "yellow", Green: "green", High: "red", Medium: "yellow", Low: "green" })[value] ?? "neutral";
}
function ratingText(id: string, value: string) {
  text(id, value);
  el(id).className = `rating-value signal ${signal(value)}`;
}
function date(value: string | null) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Invalid recorded date" : parsed.toLocaleDateString();
}
function number(value: number | null, suffix = "", multiplier = 1) {
  return value === null ? "Not recorded" : `${(value * multiplier).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
}
function money(value: number | null, currency: string | null) {
  return `${number(value)}${currency ? ` ${currency}` : ""}`;
}
function error(message: string) {
  text("error", message);
  el("error").hidden = false;
  el("loading").hidden = true;
  el("dashboard").hidden = true;
  el("refresh").toggleAttribute("disabled", !connected || !current);
}

function renderChart(rows: Dashboard["financials"]) {
  const host = el("revenue-chart");
  host.replaceChildren();
  const fullYears = rows.filter(r => r.period === "Full year" && r.revenue !== null && r.year !== null);
  const currencies = new Set(fullYears.map(r => r.currency));
  const years = new Set(fullYears.map(r => r.year));
  if (fullYears.length < 2 || currencies.size !== 1 || currencies.has(null) || years.size !== fullYears.length) {
    host.textContent = "At least two comparable, unique annual periods in one currency are required.";
    return;
  }
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 420 150");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", fullYears.map(r => `${r.year}: ${money(r.revenue, r.currency)}`).join("; "));
  const values = fullYears.map(r => r.revenue ?? 0);
  const low = Math.min(...values), high = Math.max(...values);
  const points = fullYears.map((r, i) => ({
    x: 36 + i * 348 / (fullYears.length - 1), y: high === low ? 70 : 100 - ((r.revenue ?? 0) - low) / (high - low) * 64,
    row: r,
  }));
  const line = document.createElementNS(ns, "polyline");
  line.setAttribute("points", points.map(p => `${p.x},${p.y}`).join(" "));
  line.setAttribute("class", "chart-line");
  svg.append(line);
  for (const p of points) {
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", `${p.x}`); dot.setAttribute("cy", `${p.y}`); dot.setAttribute("r", "4");
    dot.setAttribute("class", "chart-dot");
    const title = document.createElementNS(ns, "title");
    title.textContent = money(p.row.revenue, p.row.currency);
    dot.append(title);
    svg.append(dot);
    for (const [label, y] of [[`${p.row.year}`, 132], [number(p.row.revenue, "m", .000001), p.y - 12]] as const) {
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", `${p.x}`); t.setAttribute("y", `${y}`);
      t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "chart-label");
      t.textContent = label;
      svg.append(t);
    }
  }
  host.append(svg);
}

async function openSource(url: string) {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Unsafe source URL.");
    const result = await app.openLink({ url: parsed.href });
    if (result.isError) throw new Error("The host declined the source link.");
  } catch (cause) {
    console.error("Source link failed", cause);
    text("error", "Unable to open this evidence link in the MCP host.");
    el("error").hidden = false;
  }
}

function render(data: Dashboard) {
  current = data;
  el("error").hidden = true;
  el("loading").hidden = true;
  el("dashboard").hidden = false;
  el("refresh").toggleAttribute("disabled", !connected || refreshing);
  text("supplier-name", data.supplier.name);
  text("supplier-meta", `${data.supplier.code} / ${data.review.ref} / ${data.supplier.country ?? "Country not recorded"}`);
  text("master-rating", data.supplier.masterRating);
  el("master-rating").className = `big signal ${signal(data.supplier.masterRating)}`;
  text("master-description", ({ Red: "High risk", Yellow: "Medium risk", Green: "Low risk", "Not rated": "No stored rating" })[data.supplier.masterRating]);
  el("traffic").setAttribute("aria-label", `Supplier master rating: ${data.supplier.masterRating}`);
  el("traffic").querySelectorAll(".lamp").forEach(lamp => lamp.classList.toggle("active", lamp.classList.contains(signal(data.supplier.masterRating))));
  text("request-status", data.review.status);
  text("request-ref", data.review.ref);
  text("stage", `${data.review.stage}/5 - ${data.review.stageName}`);
  text("path", data.review.path);
  el("steps").replaceChildren(...Array.from({ length: 5 }, (_, i) => {
    const step = document.createElement("span");
    step.className = `step${i < data.review.stage ? " done" : ""}`;
    return step;
  }));
  const warnings = [...data.warnings];
  if (data.adverseEvents.some(e => e.severity === "High")) warnings.push("High-severity adverse events are recorded. Review the linked fictional evidence.");
  el("warnings").replaceChildren(...warnings.map(w => {
    const notice = document.createElement("div"); notice.className = "warning"; notice.textContent = w; return notice;
  }));
  ratingText("final-rating", data.review.confirmed ? data.review.finalRating : "Decision pending");
  text("final-detail", data.review.confirmed
    ? `${data.review.expired ? "Expired rating" : "Human-confirmed"} / ${date(data.review.ratingDate)}${data.review.overridden ? " / Reviewer override recorded" : ""}`
    : "No human-confirmed final rating for this request.");
  ratingText("ai-rating", data.review.preliminaryRating);
  text("coface-score", data.coface.score === null ? "Unavailable" : `${data.coface.score}/10`);
  text("coface-tier", `${data.coface.tier} risk / ${data.coface.current ? "Current assessment" : "Historical - not current"}`);
  el("coface-tier").className = `pill signal ${signal(data.coface.tier)}`;
  text("coface-date", `Assessment: ${date(data.coface.assessmentDate)} / validity window: 18 months`);
  text("credit-limit", `Historical source credit guidance: ${number(data.coface.creditLimit)} (source currency not recorded; not a new recommendation)`);
  el("company-facts").replaceChildren();
  for (const [key, value] of [
    ["Division", data.supplier.division], ["Industry", data.supplier.category],
    ["DUNS", data.supplier.duns], ["Active annual spend", number(data.supplier.annualSpend)],
  ]) {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = key ?? ""; dd.textContent = value ?? "Not recorded"; el("company-facts").append(dt, dd);
  }
  text("profile", data.profile ?? "Stored company narrative is unavailable for this access level.");
  text("attribution", data.sourceAttribution ?? "Source: Dataverse supplier master.");
  renderChart(data.financials);
  text("trend", data.trendInterpretation ?? "Recorded annual working-paper revenue only; no AI trend interpretation loaded.");
  text("history", data.ratingHistory.length
    ? `Human-confirmed review history: ${data.ratingHistory.map(r => `${date(r.date)} ${r.rating} (${r.ref})`).join("; ")}`
    : "No human-confirmed review history recorded.");
  el("financials").replaceChildren(...data.financials.map(r => {
    const tr = document.createElement("tr");
    for (const value of [
      `${r.year ?? "?"} / ${r.period ?? "Unknown"}`, money(r.revenue, r.currency),
      money(r.netIncome, r.currency), money(r.cashFlow, r.currency), number(r.leverage, "%", 100),
      number(r.liquidity, "x"), number(r.grossMargin, "%", 100),
    ]) {
      const td = document.createElement("td"); td.textContent = value; tr.append(td);
    }
    return tr;
  }));
  text("commentary-label", data.review.confirmed ? "Recorded final remarks" : "AI draft - not approved");
  text("commentary", !data.sensitiveVisible ? "Narratives may contain sensitive legal information. A LegalReader role is required."
    : (data.review.confirmed ? data.review.officialCommentary : data.review.narrativeDraft) ?? "No commentary recorded.");
  el("events").replaceChildren();
  if (!data.sensitiveVisible) {
    el("events").textContent = "Sensitive adverse information is withheld by the server. LegalReader access is required.";
  } else {
    const events = [
      ...data.adverseEvents.map(e => ({ ...e, details: e.headline })),
      ...data.nonFinancialRisks.map(e => ({ ...e, details: e.details })),
    ];
    if (!events.length) el("events").textContent = "No adverse-event or non-financial risk rows returned.";
    for (const e of events) {
      const row = document.createElement("div"); row.className = "event";
      const label = document.createElement("div"); label.className = `pill signal ${signal(e.severity)}`;
      label.textContent = `${e.severity} / ${date(e.date)}`;
      const details = document.createElement("p"); details.textContent = e.details;
      row.append(label, details);
      if (e.sourceUrl) {
        const button = document.createElement("button"); button.className = "source"; button.textContent = "View source evidence";
        button.addEventListener("click", () => void openSource(e.sourceUrl!)); row.append(button);
      }
      el("events").append(row);
    }
  }
  text("freshness", `${data.source} / fetched ${new Date(data.fetchedAt).toLocaleString()} / review modified ${date(data.review.modifiedOn)}${data.summaryGeneratedOn ? ` / stored summary v${data.summaryVersion ?? "?"} from ${date(data.summaryGeneratedOn)}` : ""}`);
}

function receive(result: ToolResult) {
  if (result.isError) {
    error("The SRM data read failed. Check the supplier/request reference and access permissions; retry to reload.");
    return;
  }
  const parsed = schema.safeParse(result.structuredContent);
  if (!parsed.success) {
    console.error("Invalid SRM tool result", parsed.error);
    error("The MCP server returned an invalid dashboard data contract.");
    return;
  }
  render(parsed.data);
}
app.ontoolresult = receive;
app.onerror = cause => { console.error("MCP App error", cause); error("MCP host communication failed. Reopen the dashboard to reconnect."); };
el("refresh").addEventListener("click", async () => {
  if (!current || refreshing || !connected) return;
  refreshing = true;
  el("refresh").toggleAttribute("disabled", true);
  text("loading", "Refreshing from Dataverse...");
  el("loading").hidden = false;
  try {
    receive(await app.callServerTool({
      name: "get_supplier_risk_dashboard",
      arguments: { supplier_code: current.supplier.code, request_ref: current.review.ref },
    }));
  } catch (cause) {
    console.error("Dashboard refresh failed", cause);
    error("Refresh failed. Previous data is hidden to avoid presenting it as current.");
  } finally {
    refreshing = false;
    el("refresh").toggleAttribute("disabled", !connected || !current);
  }
});
app.connect().then(() => {
  connected = true;
  applyTheme(app.getHostContext());
  text("loading", "Waiting for the supplier risk tool result...");
  if (current) el("refresh").toggleAttribute("disabled", false);
}).catch(cause => { console.error("MCP initialization failed", cause); error("This widget must be opened by an MCP Apps-compatible host."); });
