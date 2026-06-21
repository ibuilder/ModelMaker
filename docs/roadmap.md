# Platform evaluation & roadmap

A consolidated, honest snapshot of what's built across the three pillars + platform, and a
prioritized list of gaps. Complements the feature-level [capability matrix](capability-matrix.md),
the [platform-packaging roadmap](roadmap-platforms.md), and the [modeling-tools roadmap](roadmap-modeling-tools.md).

_Last evaluated: 2026-06-19._

## What's built (by pillar)

### 1. BIM viewer + modeling — mature
Three.js + Fragments viewer (lazy-loaded), spatial tree, layers, isolate/ghost, section
plane + section box, measure (distance/area), color-by-data, storey levels, set-origin/CRS.
Coordination: model federation, **clash** (AABB broad + mesh narrow phase, exact volume;
intra + cross-discipline) → BCF topics; markup pins/viewpoints. Documentation: 2D plans
(per storey), sections, elevations (HLR), sheet composer (SVG+PDF), grid bubbles/dimensions,
room tags. Analysis: envelope energy (UA/EUI), MEP inventory, IDS validation. 4D/5D: activity↔
element timeline, QTO + cost-code 5D. Authoring round-trip (server-side `ifcopenshell.api`):
walls, slabs, columns, beams, roofs, doors/windows, move/rotate/copy/delete, pset edit →
reconvert → reindex. Offline (local WASM, self-hosted tiles), PWA, Tauri 2 desktop shell.

### 2. GC portal — mature
69 config-driven modules. Per-module: record CRUD, party-gated **workflow transitions**,
kanban board, filter/sort, cross-module **relations/links**, comments, assignment, file
attachments, saved views (per-user), per-record PDF, CSV export. Cross-cutting: full-text
search, bulk actions, role-tailored dashboard with KPIs + "ball in your court", live
**notifications** (SSE badge), AIA G702/G703 pay-app PDF, Gantt/Line-of-Balance schedule viz.

### 3. Development proforma — mature
Sources & uses with **interest-reserve circularity**, S-curve cost draws, levered/unlevered
cash flows, XIRR/NPV/equity-multiple/yield-on-cost/dev-spread, **JV waterfall** (American/
European, pref + tiered promote, clawback), 2-variable **sensitivity** tables, **Monte Carlo**
risk (percentiles, P[≥target], histogram), actuals→re-forecast **draw bridge**, scenario CRUD
+ sharing + clone, multi-deal **portfolio** roll-up, scenario **compare**.

### Interoperability — new
A data-source **Connections** framework (one adapter pattern): **Postgres/Supabase** read-only
browse + guarded SELECT console; **Procore** two-way sync (import RFIs/submittals/change-events,
push resolved RFI status/answers back, scheduled auto-sync); **Autodesk Construction Cloud**
project/issue read. Admin **field-mapping editor** remaps external→module fields per connection;
secrets write-only + masked; admin-gated. Portable **`.mmproj` project bundles** (export/import
geometry + all data + attachments) and a **delete-project** path.

### Desktop / packaging — new
The whole platform runs in **one process** (FastAPI + SPA + SQLite, single-operator local mode,
no login) and ships as a self-contained **`.exe`** (PyInstaller; `desktop.py` + `build-desktop.ps1`)
— the free Bluebeam-style single-project app, verified booting + serving the full stack. The
Tauri 2 shell spawns it as a sidecar for a native window (CI-built; compile pending a CI run).

### Platform / identity / infra — mature
Token + httpOnly-cookie auth, bootstrap admin, **user management** (create/list/role/activate/
deactivate/reset), self-service password, deactivation revokes tokens immediately. **Project
RBAC** (viewer<reviewer<editor<admin + workflow party), member-management UI, web capability
gating. Audit log (server-side). Docker compose (dev + prod Caddy auto-HTTPS), nginx `/api`
proxy, Postgres/MinIO. **CI**: multi-suite Python gate (incl. connections/bundle/desktop/
local-mode); desktop release workflow (Win/macOS/Linux, signing-ready); GitHub Pages viewer demo.

## Competitor benchmark & gaps (2026-06)
Quick scan of the field to find where we're behind. Sources:
[Procore vs Autodesk](https://www.procore.com/compare/procore-vs-autodesk),
[Revizto best-BIM-2026](https://revizto.com/resources/blog/best-bim-software-tools-2023),
[TestFit](https://www.testfit.io/), [Northspyre](https://www.northspyre.com/real-estate-pro-forma-software).

| Competitor | Their strength | Us | Gap to close |
|---|---|---|---|
| Procore / ACC | model viewer **inside** the CM workflow (RFIs/submittals/punch on the model) | model pins + BCF + 68-module portal | parity; keep two-way Procore/ACC sync deepening |
| Revizto | real-time multi-model **coordination** | federation + clash + IDS + live presence | parity; add issue-tracker round-trip polish |
| Speckle | open BIM **data** platform / versioning | open, IFC-native, .mmproj bundles | add model **version history / diff** |
| **TestFit** | model **and proforma linked** — yield-on-cost from the layout | proforma is **manually keyed**, disconnected from the model | **★ link model → proforma** (areas/unit-count/QTO → assumptions) |
| Northspyre | predictive **cost-overrun** flagging across a portfolio | per-project rules/AI risk + Monte Carlo | portfolio-level cost-overrun forecasting |

### Top gaps to act on
- ✅ **DONE** — **Loading an IFC auto-populates the project.** Opening an IFC with a project open
  now sets it as the source model (publish) so drawings / clash / IDS / energy / exports /
  authoring light up automatically — no separate "upload source IFC" step.
- **★ Model → Proforma link (highest-value differentiator, à la TestFit).** Pull GFA / floor
  areas / unit count / structural & envelope quantities from the source IFC (we already compute
  QTO + spaces) and pre-fill the proforma assumptions (`/proforma/solve` inputs), so the deal
  underwrites against the actual model. Today the proforma is keyed by hand and never reads the
  model. *Next implementation target.*
- **Model version history / diff** (Speckle-style) — the `.mmproj` bundle + GUID-stable authoring
  already give the substrate; add per-publish snapshots + a changed-elements view.
- **Portfolio cost-overrun forecasting** (Northspyre-style) — extend the risk engine across the
  multi-deal portfolio roll-up.

## Gaps (prioritized)

### P0 — foundational
- ✅ **DONE** — **Frontend automated tests.** Vitest + happy-dom harness wired into CI
  (`apps/web/vitest.config.ts`); first suites cover the selection-set helpers and the API
  client (token/auth/persistence). Grow coverage as logic is extracted from DOM code.

### P1 — high-value, self-contained
- ✅ **DONE** — **Proforma debt sizing.** Loan is now the **lesser-of LTC / LTV / DSCR / debt
  yield** (optional caps on the Debt input); `debt_sizing` reports the binding constraint +
  actual DSCR/LTV/DY, surfaced in the proforma UI.
- ✅ **DONE** — **Password reset.** Admin-issued single-use, 1-hour reset token (no email
  infra); the user sets their own password (Sign in → "Have a reset token?"). Purpose-separated
  so it can't be used as a bearer token; single-use via a password-hash fingerprint.
- ✅ **DONE** — **Audit-log viewer.** `GET /audit` (admin, filter by action/actor/since) +
  an account-menu viewer; admin user-management actions are now audited.
- ✅ **DONE** — **Federation UI.** A "Models (federation)" panel lists every loaded model with
  a visibility toggle + remove; models load additively via Open ▾.

### P2 — meaningful, larger
- **Capacitor mobile** wrapper + touch tuning + on-site photo→BCF (per platform roadmap).
- ✅ **DONE** — **Email notifications / digests.** Stdlib `mailer` (SMTP via `AEC_SMTP_*`,
  no-op-but-logged when unconfigured); `User.email`; per-member work-queue digests with
  preview + send endpoints (admin); admin UI sets emails. Complements the in-app SSE badge.
- ✅ **DONE** — **Drawing leaders/callouts.** `element_callouts()` tags doors/windows (Tag→Name)
  with leader lines + boxed labels on plans; `plan.svg?callouts=true` + a "Plan + callouts"
  button. Verified: 27 callouts extracted from the sample house.
- ✅ **DONE** — **SSO / OIDC.** OAuth login for **Google, Microsoft (Entra), Procore** (`oauth.py`); enable per provider via `AEC_OAUTH_<P>_CLIENT_ID/_SECRET`. First SSO user bootstraps admin; SSO identities join the same RBAC layer.
- ✅ **DONE** (metrics + logs) — **Observability.** `/metrics` (Prometheus text: request
  counts/latencies by route template, in-flight, uptime) + structured JSON access logs
  (`aec.access`).
- ✅ **DONE** — **Backup/restore runbook.** `scripts/backup.sh` (pg_dump + MinIO/IFC volume
  tars → one timestamped tarball) + `scripts/restore.sh`; cron + retention + DR notes in
  `docs/deploy.md`.

### P2 — recently shipped
- ✅ **DONE** — **Interoperability** (the #1 2026 AEC gap). Connections framework
  (Postgres/Supabase/Procore/ACC), Procore **two-way** sync + scheduled auto-sync, ACC
  project/issue read, and an admin **field-mapping editor**. Verified by `test_connections`.
- ✅ **DONE** — **Free single-project desktop `.exe`** (PyInstaller one-process build) + portable
  `.mmproj` bundles + delete-project. Verified booting + serving API/SPA/SQLite standalone.
- ✅ **DONE** — **UX pass**: persona-ordered collapsible Tools panel with result modals; the
  68-module portal catalog (favorites + collapsible persona sections + filter); grouped viewer
  toolbar; model-type tags in the project picker. Backlog tracked in [ux-findings.md](ux-findings.md).

### P3 — external dependency / environment-gated
- **Tauri native-window installer** — the free `.exe` is verified; the Tauri shell now spawns it
  as a sidecar, but the Rust/CI compile is unverified locally (no toolchain) — run the **Desktop
  release** workflow to build + smoke-test it.
- **Bonsai bridge (M5)** — parametric authoring recipes are written but need Blender + Bonsai-
  MCP to run end-to-end.
- **RVT→IFC** via Autodesk APS — skeleton only; needs a paid APS account (behind a cost flag).

## Product improvement plan (audit)
A full-codebase performance/UX/competitive audit + prioritized roadmap lives in
[improvement-plan.md](improvement-plan.md) (2026-06-17). First item executed: proforma Monte
Carlo made on-demand.

## Execution order
~~P0 (web test harness)~~ ✅ → ~~P1 (debt sizing → password reset → audit viewer → federation
UI)~~ ✅ → **P2 next** → P3. Each item is independently shippable; P3 items are gated on
external accounts/hardware and are user-performed steps.

_P0 and all P1 items shipped 2026-06-17. Interoperability, the free desktop `.exe`, and the UX
pass shipped 2026-06-18. Next up: Capacitor mobile, the Tauri sidecar CI smoke build, and the
remaining UX backlog (empty-state consistency, light-mode contrast)._
