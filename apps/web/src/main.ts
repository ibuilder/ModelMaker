import "./style.css";
import { PortalUI } from "./portal/portal";
import { ProformaUI } from "./proforma/proforma";
import { ApiClient } from "./api/client";
import { toast } from "./ui/feedback";
import type { Settings, ViewerApp } from "./viewer/app";

// ---- shell DOM + shared state (no three/@thatopen here — those load lazily) --
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const container = $("container");
const statusEl = $("status");
const toolbar = $("topbar");
const setStatus = (m: string) => (statusEl.textContent = m);
const notify = (m: string, kind: "info" | "success" | "error" = "info") => { setStatus(m); toast(m, kind); };
const api = new ApiClient();

let projectId: string | null = null;
let connected = false;
let projectName = "";

// ---- lazy viewer: the heavy 3D module loads on first Model-workspace use -----
let viewerApp: ViewerApp | null = null;
let viewerLoading: Promise<ViewerApp> | null = null;
async function ensureViewer(): Promise<ViewerApp> {
  if (viewerApp) return viewerApp;
  if (!viewerLoading) {
    viewerLoading = import("./viewer/app").then(({ initViewerApp }) => {
      viewerApp = initViewerApp({
        container, api, projectId, connected, projectName,
        setStatus, notify, getSettings: () => settings,
      });
      return viewerApp;
    });
  }
  return viewerLoading;
}
const withViewer = (fn: (v: ViewerApp) => void) => void ensureViewer().then(fn);

// ---- Open / Save dropdown menus ---------------------------------------------
interface MenuItem { label: string; sep?: boolean; onClick?: () => void; }
function buildMenu(mountId: string, label: string, items: MenuItem[], onOpen?: () => void) {
  const mount = $(mountId);
  const btn = document.createElement("button");
  btn.className = "file-btn menu-btn"; btn.textContent = label;
  const panel = document.createElement("div"); panel.className = "menu-panel"; panel.hidden = true;
  for (const it of items) {
    if (it.sep) { const s = document.createElement("div"); s.className = "menu-sep"; s.textContent = it.label; panel.appendChild(s); continue; }
    const mi = document.createElement("button"); mi.className = "menu-item"; mi.textContent = it.label;
    mi.onclick = () => { panel.hidden = true; it.onClick?.(); };
    panel.appendChild(mi);
  }
  const place = () => { const r = btn.getBoundingClientRect(); panel.style.left = `${r.left}px`; panel.style.top = `${r.bottom + 4}px`; };
  btn.onclick = (e) => { e.stopPropagation(); closeMenus(panel); const open = panel.hidden; if (open) { place(); onOpen?.(); } panel.hidden = !open; };
  mount.append(btn, panel);
}
function closeMenus(keep?: Element) {
  document.querySelectorAll(".menu-panel").forEach((p) => { if (p !== keep) (p as HTMLElement).hidden = true; });
}
const dismissMenusIfOutside = (e: Event) => { if (!(e.target as HTMLElement).closest(".menu")) closeMenus(); };
document.addEventListener("pointerdown", dismissMenusIfOutside, true);
document.addEventListener("click", dismissMenusIfOutside, true);
window.addEventListener("blur", () => closeMenus());
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenus(); });
// pre-warm the viewer when the file menus open so triggerOpen/export resolve promptly
buildMenu("open-menu", "Open ▾", [
  { label: "Open IFC…", onClick: () => withViewer((v) => v.triggerOpen("ifc")) },
  { label: "Open Fragments (.frag)…", onClick: () => withViewer((v) => v.triggerOpen("frag")) },
  { label: "Sample models", sep: true },
  { label: "School — Structural", onClick: () => withViewer((v) => void v.loadSample("/school_str.frag", "School (Structural)")) },
  { label: "School — Architectural", onClick: () => withViewer((v) => void v.loadSample("/school_arq.frag", "School (Architectural)")) },
  { label: "BasicHouse", onClick: () => withViewer((v) => void v.loadSample("/basichouse.frag", "BasicHouse")) },
  { label: "Import (Autodesk — paid bridge)", sep: true },
  { label: "Revit (.rvt)…", onClick: () => withViewer((v) => v.triggerOpen("convert")) },
  { label: "AutoCAD (.dwg)…", onClick: () => withViewer((v) => v.triggerOpen("convert")) },
  { label: "Navisworks (.nwc)…", onClick: () => withViewer((v) => v.triggerOpen("convert")) },
], () => void ensureViewer());
buildMenu("save-menu", "Save ▾", [
  { label: "Export Fragments (.frag)", onClick: () => withViewer((v) => void v.exportFrag()) },
  { label: "Export source IFC (.ifc)", onClick: () => withViewer((v) => v.exportIfc()) },
], () => void ensureViewer());

// ---- workspaces + left icon rail --------------------------------------------
const appEl = document.getElementById("app")!;
const RAIL_ITEMS: { key: string; icon: string; title: string }[] = [
  { key: "tree", icon: "⌗", title: "Model tree" },
  { key: "layers", icon: "≣", title: "Layers" },
  { key: "issues", icon: "⚑", title: "Issues / RFIs" },
  { key: "tools", icon: "⚙", title: "Tools & analysis" },
];
const railEl = $("rail");
function showRail(key: string) {
  appEl.classList.remove("rail-collapsed");
  document.querySelectorAll(".rail-btn").forEach((b) => b.classList.toggle("active", (b as HTMLElement).dataset.rail === key));
  document.querySelectorAll(".rpanel").forEach((p) => p.classList.remove("active"));
  $(`panel-${key}`).classList.add("active");
}
for (const it of RAIL_ITEMS) {
  const b = document.createElement("button");
  b.className = "rail-btn"; b.dataset.rail = it.key; b.textContent = it.icon;
  b.title = it.title; b.setAttribute("aria-label", it.title);
  b.onclick = () => {
    const isActive = b.classList.contains("active") && !appEl.classList.contains("rail-collapsed");
    if (isActive) appEl.classList.add("rail-collapsed");
    else showRail(it.key);
  };
  railEl.appendChild(b);
}

const WORKSPACES: { key: string; label: string }[] = [
  { key: "model", label: "Model" }, { key: "construction", label: "Construction" }, { key: "finance", label: "Finance" },
];
let currentWs = "model";
function setWorkspace(key: string) {
  currentWs = key;
  document.querySelectorAll(".ws-btn").forEach((b) => b.classList.toggle("active", (b as HTMLElement).dataset.ws === key));
  document.querySelectorAll(".workspace").forEach((w) => w.classList.toggle("active", w.id === `ws-${key}`));
  if (key === "construction") openPortalTab();
  if (key === "finance") openProformaTab();
  if (key === "model") void ensureViewer().then((v) => v.onModelShown());   // lazy-load the 3D app
  localStorage.setItem("workspace", key);
}
const wsEl = $("workspaces");
for (const w of WORKSPACES) {
  const b = document.createElement("button");
  b.className = "ws-btn"; b.dataset.ws = w.key; b.textContent = w.label;
  b.onclick = () => setWorkspace(w.key);
  wsEl.appendChild(b);
}

document.querySelectorAll<HTMLButtonElement>(".fintab").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll(".fintab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll("#ws-finance .fullpanel").forEach((p) => p.classList.remove("active"));
    t.classList.add("active");
    $(`panel-${t.dataset.fin}`).classList.add("active");
    if (t.dataset.fin === "proforma") openProformaTab();
    if (t.dataset.fin === "portfolio") openPortfolioTab();
  };
});

// ---- role-based navigation --------------------------------------------------
interface PersonaCfg { ws: string[] | null; rail: string[] | null; home: string; }
const PERSONAS: Record<string, PersonaCfg> = {
  all:           { ws: null, rail: null, home: "model" },
  developer:     { ws: ["finance", "model", "construction"], rail: ["issues", "tools", "tree"], home: "finance" },
  gc:            { ws: ["construction", "model", "finance"], rail: ["tree", "layers", "issues", "tools"], home: "construction" },
  architect:     { ws: ["model", "construction"], rail: ["tree", "layers", "issues", "tools"], home: "model" },
  engineer:      { ws: ["model"], rail: ["tree", "layers", "tools", "issues"], home: "model" },
  subcontractor: { ws: ["construction", "model"], rail: ["issues", "tools"], home: "construction" },
};
const personaSel = document.getElementById("persona") as HTMLSelectElement;
function applyPersona(p: string, goHome = false) {
  const cfg = PERSONAS[p] ?? PERSONAS.all;
  document.querySelectorAll<HTMLButtonElement>(".ws-btn").forEach((b) => { b.hidden = !!cfg.ws && !cfg.ws.includes(b.dataset.ws!); });
  document.querySelectorAll<HTMLButtonElement>(".rail-btn").forEach((b) => { b.hidden = !!cfg.rail && !cfg.rail.includes(b.dataset.rail!); });
  const allowedRail = cfg.rail ?? RAIL_ITEMS.map((r) => r.key);
  const activeRail = document.querySelector(".rail-btn.active") as HTMLElement | null;
  if (!activeRail || !allowedRail.includes(activeRail.dataset.rail!)) showRail(allowedRail[0]);
  if (goHome || (cfg.ws && !cfg.ws.includes(currentWs))) setWorkspace(cfg.home);
  localStorage.setItem("persona", p);
}
personaSel.value = localStorage.getItem("persona") || "all";
personaSel.onchange = () => applyPersona(personaSel.value, true);

// ---- rail collapse + drag-to-resize (persisted) -----------------------------
function toggleRail() { appEl.classList.toggle("rail-collapsed"); }
(document.getElementById("rail-toggle") as HTMLButtonElement).onclick = toggleRail;
const savedW = localStorage.getItem("rail-w");
if (savedW) appEl.style.setProperty("--rail-w", savedW);
const resizer = document.createElement("div");
resizer.id = "rail-resize"; resizer.title = "Drag to resize";
$("rail-panel").appendChild(resizer);
resizer.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  resizer.setPointerCapture(e.pointerId);
  const move = (ev: PointerEvent) => {
    const w = Math.min(Math.max(ev.clientX - 46, 200), 560);
    appEl.style.setProperty("--rail-w", `${w}px`);
  };
  const up = () => {
    resizer.removeEventListener("pointermove", move);
    resizer.removeEventListener("pointerup", up);
    localStorage.setItem("rail-w", getComputedStyle(appEl).getPropertyValue("--rail-w").trim());
  };
  resizer.addEventListener("pointermove", move);
  resizer.addEventListener("pointerup", up);
});

// ---- bottom settings bar ----------------------------------------------------
const SETTINGS_DEFAULTS: Settings = {
  theme: "dark", grid: true, projection: "Perspective", background: "dark",
  zoomCursor: true, nav: "orbit", units: "m", section: false, snap: 0,
};
const settings: Settings = { ...SETTINGS_DEFAULTS, ...JSON.parse(localStorage.getItem("aec-settings") || "{}") };
let savedTimer: number | undefined;
function flashSaved() {
  const el = document.getElementById("sb-saved"); if (!el) return;
  el.classList.add("show"); clearTimeout(savedTimer);
  savedTimer = window.setTimeout(() => el.classList.remove("show"), 1200);
}
function applyTheme() { document.documentElement.dataset.theme = settings.theme === "light" ? "light" : ""; }
function onSettingsChanged() { applyTheme(); if (viewerApp) viewerApp.applySettings(); localStorage.setItem("aec-settings", JSON.stringify(settings)); flashSaved(); }

function buildStatusBar() {
  const bar = $("statusbar");
  const sep = () => { const d = document.createElement("span"); d.className = "sb-sep"; return d; };
  const toggle = (label: string, key: "grid" | "section" | "zoomCursor") => {
    const b = document.createElement("button"); b.className = "sb-toggle"; b.textContent = label;
    const sync = () => b.classList.toggle("on", !!settings[key]);
    b.onclick = () => { settings[key] = !settings[key]; sync(); onSettingsChanged(); };
    sync(); return b;
  };
  const select = (label: string, key: "projection" | "theme" | "background" | "nav" | "units", opts: [string, string][]) => {
    const wrap = document.createElement("span"); wrap.className = "sb-group";
    const l = document.createElement("label"); l.textContent = label;
    const s = document.createElement("select"); s.className = "sb-sel";
    for (const [v, t] of opts) { const o = document.createElement("option"); o.value = v; o.textContent = t; s.appendChild(o); }
    s.value = String(settings[key]);
    s.onchange = () => { (settings[key] as string) = s.value; onSettingsChanged(); };
    wrap.append(l, s); return wrap;
  };
  const fit = document.createElement("button"); fit.className = "sb-toggle"; fit.textContent = "⤢ Fit";
  fit.title = "Fit to view (F)"; fit.onclick = () => withViewer((v) => void v.fitToModels());
  bar.append(
    fit, sep(),
    toggle("Grid", "grid"), toggle("Section", "section"),
    select("View", "projection", [["Perspective", "Perspective"], ["Orthographic", "Ortho"]]), sep(),
    select("Theme", "theme", [["dark", "Dark"], ["light", "Light"]]),
    select("Background", "background", [["dark", "Dark"], ["light", "Light"], ["none", "None"]]), sep(),
    select("Nav", "nav", [["orbit", "Orbit"], ["pan", "Pan (Revit)"], ["cad", "CAD (Navis)"]]),
    toggle("Zoom to cursor", "zoomCursor"),
    select("Units", "units", [["m", "m"], ["cm", "cm"], ["mm", "mm"], ["ft", "ft-in"]]), sep(),
  );
  // grid-snap increment for authoring placement (number, so not the string select helper)
  const snapWrap = document.createElement("span"); snapWrap.className = "sb-group";
  const snapL = document.createElement("label"); snapL.textContent = "Snap";
  const snapSel = document.createElement("select"); snapSel.className = "sb-sel";
  for (const [v, t] of [["0", "off"], ["0.1", "0.1m"], ["0.5", "0.5m"], ["1", "1m"]]) {
    const o = document.createElement("option"); o.value = v; o.textContent = t; snapSel.appendChild(o);
  }
  snapSel.value = String(settings.snap);
  snapSel.onchange = () => { settings.snap = Number(snapSel.value); onSettingsChanged(); };
  snapWrap.append(snapL, snapSel);
  bar.append(snapWrap, sep());
  const coords = document.createElement("span"); coords.id = "sb-coords"; coords.textContent = "—";
  const saved = document.createElement("span"); saved.id = "sb-saved"; saved.textContent = "✓ saved";
  bar.append(coords, saved);
}

showRail("tree");
buildStatusBar();
applyTheme();

// ---- portal / proforma (light — no 3D) --------------------------------------
const portal = new PortalUI($("panel-portal"), {
  api,
  projectId: () => projectId,
  anchorPoint: () => viewerApp?.anchorPoint() ?? null,
  selectedGuid: () => viewerApp?.selectedGuidValue() ?? null,
  onSelectGuids: (guids) => { if (guids[0]) { setWorkspace("model"); withViewer((v) => void v.selectByGuid(guids[0], true)); } },
  onPinsChanged: () => { if (viewerApp) void viewerApp.reloadModelPins(); },
  setStatus,
});
let portalReady = false;
function openPortalTab() { if (portalReady) return; portalReady = true; void portal.init(); }

const proforma = new ProformaUI($("panel-proforma"), api, setStatus, () => projectId);
let proformaReady = false;
function openProformaTab() { if (proformaReady) return; proformaReady = true; void proforma.init(); }

async function openPortfolioTab() {
  const panel = $("panel-portfolio");
  panel.innerHTML = `<div class="section-title">Portfolio roll-up</div><div class="meta">loading…</div>`;
  let p;
  try { p = await api.portfolio(); }
  catch { panel.innerHTML = `<div class="meta">portfolio unavailable (API offline)</div>`; return; }
  const t = p.totals;
  const m = (v: number | null) => (v == null ? "—" : "$" + Math.round(v).toLocaleString());
  const pc = (v: number | null) => (v == null ? "—" : (v * 100).toFixed(1) + "%");
  const kpis: [string, string][] = [
    ["Deals", String(p.deal_count)], ["Total cap", m(t.total_capitalization)],
    ["Total equity", m(t.total_equity)], ["Blended LTC", pc(t.blended_ltc)],
    ["Portfolio IRR", pc(t.portfolio_irr)], ["Portfolio EM", `${t.portfolio_equity_multiple ?? "—"}×`],
  ];
  const rows = p.deals.map((d) =>
    `<tr><th style="text-align:left">${d.name}</th><td>${m(d.total_uses)}</td>` +
    `<td>${m(d.equity)}</td><td>${pc(d.equity_irr)}</td><td>${d.equity_multiple ?? "—"}×</td></tr>`).join("");
  panel.innerHTML =
    `<div class="section-title">Portfolio roll-up — ${p.deal_count} deal(s)</div>` +
    `<div class="kpi-grid">` +
    kpis.map(([l, v]) => `<div class="kpi"><div class="kpi-v" style="font-size:15px">${v}</div><div class="kpi-l">${l}</div></div>`).join("") +
    `</div>` +
    (p.deal_count ? `<table class="sens-table"><tr><th>Deal</th><th>Cap</th><th>Equity</th><th>IRR</th><th>EM</th></tr>${rows}</table>`
                  : `<div class="meta" style="margin-top:8px">No solved scenarios yet — build one in the Proforma tab and it rolls up here.</div>`);
}

function buildProjectPicker(projects: { id: string; name: string }[]) {
  const sel = document.createElement("select");
  sel.className = "tool-btn"; sel.title = "Project";
  for (const p of projects) {
    const o = document.createElement("option");
    o.value = p.id; o.textContent = p.name; o.selected = p.id === projectId;
    sel.appendChild(o);
  }
  sel.onchange = () => { window.location.search = `?project=${sel.value}`; };
  toolbar.insertBefore(sel, statusEl);
}

// ---- auth: sign-in control + modal ------------------------------------------
function loginModal() {
  const ov = document.createElement("div");
  ov.style.cssText = "position:fixed;inset:0;z-index:200;background:#000a;display:flex;align-items:center;justify-content:center";
  const card = document.createElement("div");
  card.style.cssText = "background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:20px;min-width:280px;display:flex;flex-direction:column;gap:10px";
  const title = document.createElement("strong"); title.textContent = "Sign in"; title.style.fontSize = "15px";
  const u = document.createElement("input"); u.placeholder = "username"; u.className = "portal-filter";
  const p = document.createElement("input"); p.type = "password"; p.placeholder = "password"; p.className = "portal-filter";
  const msg = document.createElement("div"); msg.className = "meta"; msg.style.color = "#e2554a";
  const row = document.createElement("div"); row.style.cssText = "display:flex;gap:8px;justify-content:flex-end";
  const cancel = document.createElement("button"); cancel.className = "tool-btn"; cancel.textContent = "Cancel"; cancel.onclick = () => ov.remove();
  const go = document.createElement("button"); go.className = "file-btn"; go.textContent = "Sign in";
  const submit = async () => {
    if (!u.value.trim() || !p.value) { msg.textContent = "enter a username and password"; return; }
    try { const r = await api.login(u.value.trim(), p.value); api.setToken(r.token); ov.remove(); location.reload(); }
    catch { msg.textContent = "invalid username or password"; }
  };
  go.onclick = () => void submit();
  p.onkeydown = (e) => { if (e.key === "Enter") void submit(); };
  row.append(cancel, go); card.append(title, u, p, msg, row); ov.append(card);
  document.body.appendChild(ov); u.focus();
}

async function buildAuthControl() {
  const el = document.createElement("button");
  el.className = "tool-btn"; el.style.marginLeft = "6px";
  if (api.authed) {
    let name = "account";
    try { const m = await api.me(); if (m.authenticated) name = m.username; else api.setToken(""); }
    catch { /* keep token; offline */ }
    el.textContent = `${name} ⏻`; el.title = "Sign out";
    el.onclick = async () => { await api.logout(); api.setToken(""); location.reload(); };
  } else {
    el.textContent = "Sign in"; el.title = "Sign in";
    el.onclick = loginModal;
  }
  toolbar.insertBefore(el, statusEl);
}

// live notification badge on the Construction workspace tab (SSE)
function connectNotifications() {
  if (!projectId) return;
  const ws = document.querySelector<HTMLElement>('.ws-btn[data-ws="construction"]');
  if (!ws) return;
  let badge = ws.querySelector<HTMLElement>(".ws-badge");
  if (!badge) { badge = document.createElement("span"); badge.className = "ws-badge"; ws.appendChild(badge); }
  try {
    api.notificationStream(projectId, ({ count }) => {
      badge!.textContent = count > 0 ? String(count) : "";
      badge!.style.display = count > 0 ? "" : "none";
    });
  } catch { /* SSE unsupported / offline */ }
}

// ---- keyboard shortcuts -----------------------------------------------------
const SHORTCUTS = "F fit · Esc clear · M dist · A area · S section · H show all · ? help";
window.addEventListener("keydown", (e) => {
  const t = e.target as HTMLElement;
  if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
  const k = e.key.toLowerCase();
  if (k === "\\") { toggleRail(); return; }
  if (k === "?") { toast(SHORTCUTS + " · \\ panel", "info", 6000); return; }
  if (["f", "escape", "m", "a", "s", "h"].includes(k) && viewerApp) viewerApp.handleKey(k);
});

// ---- startup ----------------------------------------------------------------
async function startup() {
  connected = await api.health();
  let projects: { id: string; name: string }[] = [];
  if (connected) {
    projects = await api.projects();
    const wanted = new URLSearchParams(location.search).get("project");
    const chosen = projects.find((p) => p.id === wanted) ?? projects[0];
    projectId = chosen?.id ?? null;
    projectName = chosen?.name ?? "";
    setStatus(projectId ? `connected • ${projectName}` : "connected • no project");
    if (projects.length) buildProjectPicker(projects);
  } else {
    setStatus("offline — open a .frag to view (API not reachable)");
  }
  if (projectId) connectNotifications();
  void buildAuthControl();
}

function initNav() {
  applyPersona(personaSel.value);
  const savedWs = localStorage.getItem("workspace");
  const allowWs = PERSONAS[personaSel.value]?.ws ?? null;
  setWorkspace(savedWs && (!allowWs || allowWs.includes(savedWs)) ? savedWs : currentWs);
}

startup().finally(initNav);
