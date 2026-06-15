import type { ApiClient, ModuleDef } from "../api/client";

/**
 * GC portal UI — one config-driven engine renders every module's list / form / record pages
 * from its module.json (fetched at /modules). No per-module code: the same views drive RFIs,
 * the change-order chain, daily reports, etc. Workflow actions are server-gated by party role.
 */
export interface PortalHost {
  api: ApiClient;
  projectId: () => string | null;
  anchorPoint: () => { x: number; y: number; z: number } | null;  // last clicked 3D point
  selectedGuid: () => string | null;
  onSelectGuids: (guids: string[]) => void;                       // highlight in 3D
  onPinsChanged: () => void;                                      // refresh model pins
  setStatus: (m: string) => void;
}

export class PortalUI {
  private mods: ModuleDef[] = [];

  constructor(private root: HTMLElement, private host: PortalHost) {}

  async init() {
    if (!this.host.projectId()) { this.root.textContent = "connect a project to use the portal"; return; }
    this.mods = await this.host.api.modules();
    this.renderHome();
  }

  // --- module catalog grouped by section -------------------------------------
  private renderHome() {
    this.root.innerHTML = "";
    const sections = new Map<string, ModuleDef[]>();
    for (const m of this.mods) {
      const s = m.section || "Other";
      (sections.get(s) ?? sections.set(s, []).get(s)!).push(m);
    }
    for (const [section, mods] of sections) {
      const h = document.createElement("div");
      h.className = "section-title"; h.textContent = section;
      this.root.appendChild(h);
      for (const m of mods) {
        const b = document.createElement("button");
        b.className = "portal-mod";
        b.innerHTML = `<span class="ic">${m.icon || "•"}</span> ${m.name}`;
        b.onclick = () => this.openModule(m);
        this.root.appendChild(b);
      }
    }
  }

  // --- record list -----------------------------------------------------------
  private async openModule(m: ModuleDef) {
    const pid = this.host.projectId()!;
    const records = await this.host.api.moduleRecords(pid, m.key);
    this.root.innerHTML = "";
    this.root.appendChild(this.bar(m.name, () => this.renderHome()));

    const newBtn = document.createElement("button");
    newBtn.className = "tool-btn"; newBtn.textContent = "+ New"; newBtn.style.margin = "6px 0";
    newBtn.onclick = () => this.renderForm(m);
    this.root.appendChild(newBtn);

    if (!records.length) {
      const e = document.createElement("div"); e.className = "meta"; e.textContent = "no records yet";
      this.root.appendChild(e);
      return;
    }
    const table = document.createElement("table"); table.className = "portal-table";
    table.innerHTML = "<thead><tr><th>Ref</th><th>Title</th><th>Status</th></tr></thead>";
    const tb = document.createElement("tbody");
    for (const r of records) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.ref}</td><td>${r.title ?? ""}</td>` +
        `<td><span class="badge">${r.workflow_state}</span></td>`;
      tr.onclick = () => this.openRecord(m, r.id);
      tb.appendChild(tr);
    }
    table.appendChild(tb);
    this.root.appendChild(table);
  }

  // --- create form (fields from module.json) ---------------------------------
  private renderForm(m: ModuleDef) {
    this.root.innerHTML = "";
    this.root.appendChild(this.bar(`New ${m.name}`, () => this.openModule(m)));
    const inputs: Record<string, HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement> = {};
    for (const f of m.fields) {
      const wrap = document.createElement("label"); wrap.className = "portal-field";
      wrap.textContent = f.label + (f.required ? " *" : "");
      let el: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
      if (f.type === "textarea") el = document.createElement("textarea");
      else if (f.type === "select") {
        el = document.createElement("select");
        for (const o of f.options ?? []) { const opt = document.createElement("option"); opt.value = opt.textContent = o; el.appendChild(opt); }
      } else { el = document.createElement("input"); (el as HTMLInputElement).type = f.type === "number" ? "number" : f.type === "date" ? "date" : "text"; }
      inputs[f.name] = el; wrap.appendChild(el); this.root.appendChild(wrap);
    }
    // pin-to-model option
    const pinLabel = document.createElement("label"); pinLabel.className = "portal-field";
    const pinCb = document.createElement("input"); pinCb.type = "checkbox"; pinCb.checked = m.pinnable;
    pinLabel.append(pinCb, document.createTextNode(" Pin to last-clicked model point"));
    if (m.pinnable) this.root.appendChild(pinLabel);

    const save = document.createElement("button");
    save.className = "file-btn"; save.textContent = "Create"; save.style.marginTop = "8px";
    save.onclick = async () => {
      const data: Record<string, unknown> = {};
      for (const f of m.fields) { const v = inputs[f.name].value; if (v) data[f.name] = f.type === "number" ? Number(v) : v; }
      const body: Record<string, unknown> = { data };
      if (m.pinnable && pinCb.checked) {
        body.anchor = this.host.anchorPoint();
        const g = this.host.selectedGuid(); if (g) body.element_guids = [g];
      }
      try {
        const rec = await this.host.api.createModuleRecord(this.host.projectId()!, m.key, body);
        this.host.setStatus(`created ${rec.ref}`);
        if (body.anchor) this.host.onPinsChanged();
        this.openRecord(m, rec.id);
      } catch (e) { this.host.setStatus(`error: ${(e as Error).message}`); }
    };
    this.root.appendChild(save);
  }

  // --- record detail + workflow actions + activity ---------------------------
  private async openRecord(m: ModuleDef, rid: string) {
    const pid = this.host.projectId()!;
    const r = await this.host.api.moduleRecord(pid, m.key, rid);
    this.root.innerHTML = "";
    this.root.appendChild(this.bar(`${r.ref}`, () => this.openModule(m)));

    const head = document.createElement("div");
    head.innerHTML = `<div class="portal-rec-title">${r.title ?? r.ref}</div>` +
      `<div class="meta">status <span class="badge">${r.workflow_state}</span> · ${r.party_owner ?? ""}</div>`;
    this.root.appendChild(head);

    // fields
    const fields = document.createElement("div"); fields.className = "portal-kv";
    for (const f of m.fields) {
      const v = r.data[f.name];
      if (v === undefined || v === "") continue;
      fields.insertAdjacentHTML("beforeend", `<div class="k">${f.label}</div><div class="v">${v}</div>`);
    }
    this.root.appendChild(fields);

    // anchor / linked elements
    if (r.element_guids?.length) {
      const b = document.createElement("button"); b.className = "tool-btn"; b.textContent = "Show in model";
      b.style.margin = "4px 0"; b.onclick = () => this.host.onSelectGuids(r.element_guids!);
      this.root.appendChild(b);
    }

    // workflow actions (server-gated by party)
    const acts = r.available_actions ?? [];
    if (acts.length) {
      const ad = document.createElement("div"); ad.className = "section-title"; ad.textContent = "Workflow";
      this.root.appendChild(ad);
      for (const a of acts) {
        const b = document.createElement("button"); b.className = "tool-btn";
        b.textContent = `${a.action} → ${a.to}`; b.style.cssText = "display:block;margin:3px 0;width:100%;text-align:left";
        b.onclick = async () => {
          try { await this.host.api.transitionRecord(pid, m.key, rid, a.action); this.openRecord(m, rid); }
          catch (e) { this.host.setStatus(`blocked: ${(e as Error).message}`); }
        };
        this.root.appendChild(b);
      }
    }

    // linked records (change-order chain)
    if (r.links?.length) {
      const ld = document.createElement("div"); ld.className = "section-title"; ld.textContent = "Linked";
      this.root.appendChild(ld);
      for (const l of r.links) {
        const e = document.createElement("div"); e.className = "meta"; e.textContent = `${l.module}: ${l.ref}`;
        this.root.appendChild(e);
      }
    }

    // activity timeline
    const td = document.createElement("div"); td.className = "section-title"; td.textContent = "Activity";
    this.root.appendChild(td);
    for (const a of r.activity ?? []) {
      const e = document.createElement("div"); e.className = "portal-act";
      e.textContent = `${(a.ts || "").slice(0, 16).replace("T", " ")} · ${a.actor ?? ""} · ${a.action}`;
      this.root.appendChild(e);
    }
  }

  private bar(title: string, back: () => void): HTMLElement {
    const bar = document.createElement("div"); bar.className = "portal-bar";
    const b = document.createElement("button"); b.className = "tool-btn"; b.textContent = "←";
    b.onclick = back;
    const t = document.createElement("strong"); t.textContent = title;
    bar.append(b, t);
    return bar;
  }
}
