import type { ApiClient } from "../api/client";

/** 2D Drawings Set — a sheet-set browser for the server-generated plans / elevations / sections
 *  (cf. PlanGrid plan room + Bluebeam markup + Fieldlens field pins). Left: a sheet register;
 *  right: a pan/zoom drawing viewer with a markup layer (numbered pins + notes). */

interface DrawingsHost {
  api: ApiClient;
  projectId: () => string | null;
  setStatus: (m: string) => void;
}

interface Sheet {
  id: string;                 // stable key (also the markup key)
  label: string;
  type: "plan" | "elevation" | "section" | "sheet";
  path: string;               // SVG endpoint (query string included)
  pdf?: string;               // optional PDF download
}

interface Pin { x: number; y: number; note: string }

const DIRS = ["north", "south", "east", "west"] as const;

export class DrawingsUI {
  private root: HTMLElement;
  private stage!: HTMLElement;      // transformed content (SVG + pins)
  private svgHost!: HTMLElement;
  private pinLayer!: HTMLElement;
  private tx = 0; private ty = 0; private scale = 1;
  private current?: Sheet;
  private callouts = false;
  private markupOn = false;

  constructor(host: HTMLElement, private host_: DrawingsHost) { this.root = host; }

  /** Build the workspace (idempotent) and load the sheet register for the active project. */
  async open(): Promise<void> {
    if (!this.root.childElementCount) this.build();
    await this.loadRegister();
  }

  private build() {
    this.root.innerHTML = "";
    this.root.classList.add("dwg-wrap");
    const side = document.createElement("div"); side.className = "dwg-side";
    side.innerHTML = `<div class="section-title">Drawing set</div>`;
    const list = document.createElement("div"); list.id = "dwg-list"; side.appendChild(list);

    const main = document.createElement("div"); main.className = "dwg-main";
    const bar = document.createElement("div"); bar.className = "dwg-toolbar"; bar.id = "dwg-toolbar";
    const viewport = document.createElement("div"); viewport.className = "dwg-viewport";
    this.stage = document.createElement("div"); this.stage.className = "dwg-stage";
    this.svgHost = document.createElement("div"); this.svgHost.className = "dwg-svg";
    this.pinLayer = document.createElement("div"); this.pinLayer.className = "dwg-pins";
    this.stage.append(this.svgHost, this.pinLayer);
    viewport.appendChild(this.stage);
    main.append(bar, viewport);
    this.root.append(side, main);

    this.wirePanZoom(viewport);
    bar.innerHTML = `<span class="meta" id="dwg-title">Select a sheet</span>`;
  }

  private async loadRegister() {
    const pid = this.host_.projectId();
    const list = this.root.querySelector<HTMLElement>("#dwg-list")!;
    list.innerHTML = "";
    if (!pid) { list.innerHTML = `<div class="meta">connect a project to view drawings</div>`; return; }
    const pq = (s: Record<string, string | number>) =>
      Object.entries(s).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");

    const sheets: Sheet[] = [];
    let storeys: { name: string; elevation: number }[] = [];
    try { storeys = await this.host_.api.drawingStoreys(pid); } catch { /* no source IFC */ }
    for (const s of storeys) {
      const q = pq({ elevation: s.elevation, cut_height: 1.2, title: `PLAN - ${s.name}` });
      sheets.push({ id: `plan:${s.name}`, label: `Plan — ${s.name}`, type: "plan",
                    path: `/projects/${pid}/drawings/plan.svg?${q}` });
    }
    for (const d of DIRS) {
      sheets.push({ id: `elev:${d}`, label: `Elevation — ${d[0].toUpperCase()}${d.slice(1)}`, type: "elevation",
                    path: `/projects/${pid}/drawings/elevation.svg?direction=${d}` });
    }
    sheets.push({ id: "sec:AA", label: "Section A-A", type: "section",
                  path: `/projects/${pid}/drawings/section.svg?axis=x&offset=27&title=${encodeURIComponent("SECTION A-A")}` });
    sheets.push({ id: "sheet:S-101", label: "Sheet S-101 (composed)", type: "sheet",
                  path: `/projects/${pid}/drawings/sheet.svg?sheet=S-101`,
                  pdf: `/projects/${pid}/drawings/sheet.pdf?sheet=S-101` });

    if (!storeys.length) {
      const note = document.createElement("div"); note.className = "meta";
      note.textContent = "No storeys (needs a source IFC) — elevations/section still render from the model.";
      list.appendChild(note);
    }
    const group = (title: string, items: Sheet[]) => {
      if (!items.length) return;
      const h = document.createElement("div"); h.className = "dwg-group"; h.textContent = title; list.appendChild(h);
      for (const sh of items) {
        const b = document.createElement("button"); b.className = "dwg-item"; b.textContent = sh.label;
        b.onclick = () => { list.querySelectorAll(".dwg-item").forEach((x) => x.classList.remove("active")); b.classList.add("active"); void this.show(sh); };
        list.appendChild(b);
      }
    };
    group("Plans", sheets.filter((s) => s.type === "plan"));
    group("Elevations", sheets.filter((s) => s.type === "elevation"));
    group("Sections", sheets.filter((s) => s.type === "section"));
    group("Sheets", sheets.filter((s) => s.type === "sheet"));

    // auto-open the first available sheet
    const first = list.querySelector<HTMLButtonElement>(".dwg-item");
    if (first) { first.classList.add("active"); void this.show(sheets[0]); }
  }

  private async show(sheet: Sheet) {
    this.current = sheet;
    this.buildToolbar();
    this.svgHost.innerHTML = `<div class="meta" style="padding:20px">rendering ${sheet.label}…</div>`;
    const url = this.host_.api.url(sheet.path) + (this.callouts && sheet.type === "plan" ? "&callouts=true" : "");
    try {
      const res = await fetch(url, { headers: this.host_.api.authHeaders() });
      if (!res.ok) throw new Error(String(res.status));
      this.svgHost.innerHTML = await res.text();
      const svg = this.svgHost.querySelector("svg");
      if (svg) { svg.removeAttribute("width"); svg.removeAttribute("height"); svg.style.display = "block"; }
      this.fit();
      this.renderPins();
      this.host_.setStatus(`drawing: ${sheet.label}`);
    } catch (e) {
      this.svgHost.innerHTML = `<div class="meta" style="padding:20px;color:#e2554a">couldn't render ${sheet.label} (${(e as Error).message}) — needs a published model / source IFC.</div>`;
    }
  }

  private buildToolbar() {
    const bar = this.root.querySelector<HTMLElement>("#dwg-toolbar")!;
    bar.innerHTML = "";
    const sheet = this.current!;
    const title = document.createElement("span"); title.className = "dwg-name"; title.textContent = sheet.label;
    const spacer = () => { const s = document.createElement("span"); s.style.flex = "1"; return s; };
    const btn = (label: string, title2: string, fn: () => void, on = false) => {
      const b = document.createElement("button"); b.className = "tool-btn" + (on ? " on" : ""); b.textContent = label; b.title = title2; b.onclick = () => fn();
      return b;
    };
    bar.append(title, spacer(),
      btn("−", "Zoom out", () => this.zoom(1 / 1.2)),
      btn("⤢", "Fit", () => this.fit()),
      btn("+", "Zoom in", () => this.zoom(1.2)));
    if (sheet.type === "plan") {
      bar.append(btn("◳ Callouts", "Toggle room/element callouts", () => { this.callouts = !this.callouts; void this.show(sheet); }, this.callouts));
    }
    bar.append(
      btn("✎ Markup", "Drop pins + notes on the sheet", () => { this.markupOn = !this.markupOn; this.root.querySelector(".dwg-viewport")!.classList.toggle("marking", this.markupOn); this.buildToolbar(); }, this.markupOn),
      btn("↓ SVG", "Download SVG", () => window.open(this.host_.api.url(sheet.path), "_blank")));
    if (sheet.pdf) bar.append(btn("↓ PDF", "Download PDF", () => window.open(this.host_.api.url(sheet.pdf!), "_blank")));
  }

  // --- pan / zoom ------------------------------------------------------------
  private apply() { this.stage.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.scale})`; }

  private fit() {
    const vp = this.root.querySelector<HTMLElement>(".dwg-viewport")!;
    const svg = this.svgHost.querySelector("svg");
    const vb = svg?.viewBox?.baseVal;
    const w = vb?.width || svg?.clientWidth || 1000, h = vb?.height || svg?.clientHeight || 800;
    const pad = 24;
    this.scale = Math.min((vp.clientWidth - pad) / w, (vp.clientHeight - pad) / h) || 1;
    this.svgHost.style.width = `${w}px`; this.svgHost.style.height = `${h}px`;
    this.tx = (vp.clientWidth - w * this.scale) / 2; this.ty = (vp.clientHeight - h * this.scale) / 2;
    this.apply();
  }

  private zoom(f: number, cx?: number, cy?: number) {
    const vp = this.root.querySelector<HTMLElement>(".dwg-viewport")!.getBoundingClientRect();
    const px = (cx ?? vp.width / 2), py = (cy ?? vp.height / 2);
    const ns = Math.max(0.05, Math.min(20, this.scale * f));
    // keep the point under the cursor stationary
    this.tx = px - (px - this.tx) * (ns / this.scale);
    this.ty = py - (py - this.ty) * (ns / this.scale);
    this.scale = ns; this.apply();
  }

  private wirePanZoom(vp: HTMLElement) {
    let dragging = false, sx = 0, sy = 0, moved = false;
    vp.addEventListener("pointerdown", (e) => {
      if (this.markupOn && (e.target === this.pinLayer || this.svgHost.contains(e.target as Node))) return; // markup handles clicks
      dragging = true; moved = false; sx = e.clientX - this.tx; sy = e.clientY - this.ty; vp.setPointerCapture(e.pointerId); vp.classList.add("grabbing");
    });
    vp.addEventListener("pointermove", (e) => { if (!dragging) return; this.tx = e.clientX - sx; this.ty = e.clientY - sy; moved = true; this.apply(); });
    vp.addEventListener("pointerup", () => { dragging = false; vp.classList.remove("grabbing"); });
    vp.addEventListener("wheel", (e) => { e.preventDefault(); const r = vp.getBoundingClientRect(); this.zoom(e.deltaY < 0 ? 1.1 : 1 / 1.1, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
    // markup: click on the stage drops a pin (in content coords)
    vp.addEventListener("click", (e) => {
      if (!this.markupOn || moved || !this.current) return;
      const r = vp.getBoundingClientRect();
      const x = (e.clientX - r.left - this.tx) / this.scale;
      const y = (e.clientY - r.top - this.ty) / this.scale;
      const note = prompt("Markup note:"); if (note == null) return;
      const pins = this.pins(); pins.push({ x, y, note }); this.savePins(pins); this.renderPins();
    });
  }

  // --- markup pins (client-side, persisted per project+sheet) ----------------
  private markupKey() { return `aec-markup:${this.host_.projectId()}:${this.current?.id}`; }
  private pins(): Pin[] { try { return JSON.parse(localStorage.getItem(this.markupKey()) || "[]"); } catch { return []; } }
  private savePins(p: Pin[]) { localStorage.setItem(this.markupKey(), JSON.stringify(p)); }

  private renderPins() {
    this.pinLayer.innerHTML = "";
    const pins = this.pins();
    pins.forEach((p, i) => {
      const el = document.createElement("div"); el.className = "dwg-pin"; el.textContent = String(i + 1);
      el.style.left = `${p.x}px`; el.style.top = `${p.y}px`; el.title = p.note;
      el.onclick = (e) => {
        e.stopPropagation();
        const next = prompt(`Markup #${i + 1} (blank to delete):`, p.note);
        if (next == null) return;
        const cur = this.pins();
        if (!next.trim()) cur.splice(i, 1); else cur[i] = { ...cur[i], note: next };
        this.savePins(cur); this.renderPins();
      };
      this.pinLayer.appendChild(el);
    });
    const t = this.root.querySelector<HTMLElement>("#dwg-toolbar .dwg-name");
    if (t && pins.length) t.textContent = `${this.current!.label}  ·  ${pins.length} markup${pins.length > 1 ? "s" : ""}`;
  }
}
