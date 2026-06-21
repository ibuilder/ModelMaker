# Plan to compete (2026-06)

How AEC BIM Platform wins against the field, and the release motion behind it. Pairs with the
competitor landscape + gaps in [roadmap.md](roadmap.md).

## Positioning — one platform, open, IFC-native, no per-seat
Most competitors own one slice: Procore/ACC (GC PM), Mastt/PMWeb (owner controls), Buildertrend
(residential), Fieldwire (field/punch), Planera/P6 (CPM), Sage/STACK (precon), Viewpoint/CMiC
(ERP). We span **BIM viewer + 71-tool GC portal + development proforma in one app**, keyed off the
**IFC GlobalId** so geometry, issues, records, cost, and schedule stay in sync — and it's **open,
self-hostable, and free to run on one machine**. That combination is the wedge.

### The differentiators to lead with
1. **Model → money & schedule.** The IFC drives the build *and* the deal: takeoff → priced
   **estimate** → **budget**; areas → **proforma** hard cost/rent; activities → **CPM** float &
   critical path (a gap even Procore has). Competitors silo these.
2. **Free, offline, single-project `.exe`** (Bluebeam-style) — no Docker, no login, no per-seat.
   Lowers adoption to zero-friction; the paid tier is the cloud, not the app.
3. **Open + IFC-native + BCF round-trip** — no lock-in; coexists with ACC/Procore/Solibri via the
   Connections framework (Procore/ACC two-way, QuickBooks/Sage/Viewpoint ERP) instead of replacing.
4. **Owner / dev-manager angle** — risk register, construction **program portfolio** with
   cost-overrun flagging, and the proforma make us credible to owners/PM-consultants (Mastt/INGENIOUS
   territory) *and* the GC — one tool for both sides of the table.

## Target segments (initial wedge → expand)
- **Owner's-rep / development manager** — needs portfolio cost/risk + proforma + light GC oversight.
  We're uniquely whole-lifecycle here. **Primary.**
- **Small–mid GC** priced out of Procore's seat model — the free `.exe` + self-host is the hook.
- **Residential builder** — selections + client approval + AIA billing (Buildertrend overlap).

## Where we still trail (keep closing — from the roadmap)
- Deep **mobile field** app (Fieldwire/PlanGrid) — Capacitor wrapper is the next platform target.
- **Enterprise estimating/takeoff** depth (Sage/STACK) — we have conceptual model takeoff; assembly
  takeoff + rate libraries next.
- **ITB distribution + lead intelligence** (BuildingConnected/Dodge) — we have bid leveling; outbound
  invitations next.
- **Branded/signable PDFs** and **changed-geometry diff** — polish.

## Go-to-market & pricing
- **Free forever:** the local single-project `.exe` (full GC + proforma + viewer, offline).
- **Pro (paid cloud):** multi-project, hosted Postgres/MinIO, SSO, connectors (Procore/ACC/ERP),
  team RBAC, program portfolio, auto-update channel. Per-project or per-org, not per-seat.
- **Open core:** the platform stays open; the managed cloud + premium connectors are the revenue.
- **Distribution:** GitHub Releases (signed installers + auto-update) + the Pages landing page;
  the demo runs in-browser to remove the "book a demo" wall every competitor hides behind.

## Release motion (so a new `.exe` ships on demand)
- **Versioned, signed, auto-updating.** Bump `apps/web/package.json` + `src-tauri/tauri.conf.json`,
  tag `vX.Y.Z` → the **Desktop release** workflow builds signed Win/macOS/Linux installers + the
  in-app updater `latest.json`; installed apps self-update on launch (proven with v0.1.2).
- **Cadence:** cut a release whenever a user-visible batch lands (this session added CPM, estimating,
  ERP connectors, risk/selections/bid-leveling, TRIR, templates, version history → **cut v0.1.3**).
- **Quality gate:** `services/api/run_tests.py` (Python suites) + web tsc/vitest/build must be green
  before tagging; the in-app **update banner** also notifies users who can't auto-update.
