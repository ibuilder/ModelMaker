# Platform evaluation & roadmap

A consolidated, honest snapshot of what's built across the three pillars + platform, and a
prioritized list of gaps. Complements the feature-level [capability matrix](capability-matrix.md),
the [platform-packaging roadmap](roadmap-platforms.md), and the [modeling-tools roadmap](roadmap-modeling-tools.md).

_Last evaluated: 2026-06-17._

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
68 config-driven modules. Per-module: record CRUD, party-gated **workflow transitions**,
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

### Platform / identity / infra — mature
Token + httpOnly-cookie auth, bootstrap admin, **user management** (create/list/role/activate/
deactivate/reset), self-service password, deactivation revokes tokens immediately. **Project
RBAC** (viewer<reviewer<editor<admin + workflow party), member-management UI, web capability
gating. Audit log (server-side). Docker compose (dev + prod Caddy auto-HTTPS), nginx `/api`
proxy, Postgres/MinIO. **CI**: 8-suite Python gate; desktop release workflow (Win/macOS/Linux,
signing-ready); GitHub Pages viewer demo.

## Gaps (prioritized)

### P0 — foundational
- **Frontend has zero automated tests.** The web app is typechecked (`tsc`) but has no unit/
  component/e2e tests; all behavioral coverage is Python-side. Add a runner (Vitest) + tests
  for pure logic (capability ranking, base-path resolution, client URL building, model-id
  mapping) and wire into CI. _Highest leverage: unblocks confident frontend change._

### P1 — high-value, self-contained
- **Proforma debt sizing.** Debt is sized by LTC only; add the standard **lesser-of LTC / LTV
  / DSCR (or debt yield)** constraint so the loan responds to value and coverage, not just cost.
- **Forgot-password / password-reset flow** (email or admin-issued one-time token) — today only
  an admin can reset another user's password; there's no self-recovery.
- **Audit-log viewer UI.** The server records an audit trail; expose an admin read-only view
  (filter by actor/action/date) instead of DB-only access.
- **Federation UI.** A discipline picker to load several `.frag` and toggle by model (the
  engine already federates; the UI loads one model at a time).

### P2 — meaningful, larger
- **Capacitor mobile** wrapper + touch tuning + on-site photo→BCF (per platform roadmap).
- **Email notifications / digests** to complement the in-app SSE badge.
- **Drawing leaders/callouts** — extend room tags with leader lines + element callouts.
- **SSO / OIDC** integration for enterprise identity (current auth is self-contained).
- **Observability** — structured logs + metrics endpoint; tested backup/restore runbook.

### P3 — external dependency / environment-gated
- **Desktop installers** must be built once on a Rust machine / via the CI workflow to verify
  the Tauri compile (config + icons + workflow are ready; the compile itself is unverified here).
- **Bonsai bridge (M5)** — parametric authoring recipes are written but need Blender + Bonsai-
  MCP to run end-to-end.
- **RVT→IFC** via Autodesk APS — skeleton only; needs a paid APS account (behind a cost flag).

## Execution order
P0 (web test harness) → P1 (debt sizing → password reset → audit viewer → federation UI) →
P2 → P3. Each item is independently shippable; P3 items are gated on external accounts/hardware
and are user-performed steps.
