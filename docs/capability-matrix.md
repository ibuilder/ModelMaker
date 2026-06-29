# Capability matrix — this platform vs. Bonsai / Revit / Navisworks

Maps the BIM Software Capability Matrix to what this open platform implements. **Built** =
working + verified here; **Bridge** = via the Blender/Bonsai desktop editor (Phase 6);
**Paid** = optional Autodesk APS; **Out of scope** = not pursued.

| Capability | Bonsai | Revit | Navisworks | **This platform** |
|---|---|---|---|---|
| **MODELING & AUTHORING** | | | | |
| Parametric model authoring | Yes | Native | No | **Bridge** (Blender+Bonsai via Bonsai-MCP) |
| Native IFC authoring (model IS IFC) | Native | No | No | **Built (headless)** — `ifcopenshell.api` recipes + `/edit` round-trip; **Bridge** for GUI |
| Parametric families / components | Partial | Native | No | **Built** — `place_type` recipe instantiates IFC types; `families/` libraries; **Bridge** for parametric authoring |
| Parametric stairs/roofs/complex | Yes | Yes | No | **Bridge** |
| **DOCUMENTATION** | | | | |
| Construction drawings (plans/sections) | Partial | Native | No | **Built** — IFC section-cut → SVG plans (per storey) + sections |
| Schedules / takeoff tied to model | Yes | Yes | Yes | **Built** — QTO + generic schedule export |
| Sheet sets & title blocks | Partial | Yes | No | **Built** — sheet composer (multi-view + title block) → SVG + PDF |
| **COORDINATION & REVIEW** | | | | |
| Model federation (combine models) | Partial | Partial | Native | **Built (verified)** — multi `.frag` load (structural + architectural disciplines), per-model layers |
| **Clash detection** | Yes | Partial | Native | **Built** — AABB broad + **mesh narrow phase** (exact volume); intra-model **and cross-discipline (federated)** → BCF clash topics |
| Markup / redline / viewpoints | Partial | Partial | Yes | **Built** — BCF pins/viewpoints, restore |
| Real-time nav of huge models | Yes | Partial | Yes | **Built** — Fragments streaming + culling |
| **4D / 5D** | | | | |
| 4D scheduling | Yes | Partial | Native | **Built** — activity↔element mapping, timeline data |
| 5D quantification / cost | Yes | Partial | Yes | **Built** — QTO + cost-code map + geometry fallback |
| **ANALYSIS & QA** | | | | |
| Structural / load visualization | Yes | Yes | No | **Built (partial)** — color-by-data overlay |
| Energy / MEP systems analysis | No | Yes | No | **Built** — envelope energy model (UA + degree-day → loads/EUI from real geometry) + MEP inventory |
| **IDS / model validation (QA)** | Yes | Partial | Partial | **Built** — ifctester, → highlight failures |
| Photorealistic rendering | Yes | Partial | Yes | **Bridge** (Blender render engine) |
| **INTEROP & AUTOMATION** | | | | |
| IFC import/export | Native | Yes | Yes | **Built** — IFC→Fragments; BCF in/out |
| Vendor-neutral / openBIM | Yes | No | No | **Built** — IFC + BCF + IDS throughout |
| Scripting / API | Yes | Yes | Partial | **Built** — FastAPI + Python; MCP bridge |
| **COLLABORATION & COST** | | | | |
| Multi-user / cloud collab | Partial | Yes | Partial | **Built** — server API + project-scoped RBAC (viewer/reviewer/editor/admin), audit log; Postgres/MinIO stack |
| Licensing | Free | Paid | Paid | **Free / open** (GPL editor kept separate) |
| **CONSTRUCTION ANALYTICS** (read-side rollups; each a live tool + PDF/Excel report) | | | | |
| Quality dashboard (pass-rate, NCR loop, deficiency ball-in-court) | No | No | No | **Built** — `quality.py` |
| RFI / submittal registers (ball-in-court, overdue, turnaround) | Partial | No | No | **Built** — `rfi.py`, `submittals.py` |
| T&M rollup tied to change events → CO → billing | No | No | No | **Built** — `tm.py` (field T&M → change-event → CO) |
| Field-log rollup (manpower / weather lost-days / coverage) | Partial | No | No | **Built** — `dailylog.py` |
| OSHA safety dashboard (TRIR / DART / LTIFR) | No | No | No | **Built** — `safety.py` |
| Closeout dashboard (punchlist BIC, Cx, warranties, O&M) | Partial | No | No | **Built** — `closeout.py` |
| Executive project-health rollup (per-domain RAG + score) | No | No | No | **Built** — `projecthealth.py` |
| **OPERATE / ASSET MANAGEMENT** | | | | |
| Operating rent roll (occupancy / WALT / in-place income) | No | No | No | **Built** — `rentroll.py` |
| Lease management (renewals · escalations · CAM recovery) | No | No | No | **Built** — `leasemgmt.py` |
| Investor cap table + equity-waterfall distribution scenarios | No | No | No | **Built** — `capital.py` + `distwaterfall.py` (pref→RoC→promote, per-investor) |
| Investor-portal signed statement sharing (no-login) | No | No | No | **Built** — HMAC-signed `statement.public.pdf` |
| **DISPOSITION & VALUATION** | | | | |
| Listing / marketing kit (RESO-aligned) | No | No | No | **Built** — `marketing.py`, model+proforma autofill + Listing Fact Sheet + Marketing Flyer PDF + signed public link/QR |
| Appraisal (cost + income + sales-comp) | No | No | No | **Built** — `appraisal.py`, tri-approach reconciled, Valuation tab + PDF/Excel |
| Comparables import (CSV / RESO) | No | No | No | **Built** — `comps.py` (forgiving header map, feeds sales approach) |
| MLS / WPRealWise listing syndication (RESO) | No | No | No | **Built** — `re_bridge.py` (feature-flagged outbound push) |
| **OBSERVABILITY / OPS** | | | | |
| Prometheus metrics + healthchecks | No | No | No | **Built** — `/metrics`, `/health` + `/ready`, compose healthchecks; non-root API container |
| Backup / restore runbook | No | No | No | **Built** — `scripts/backup.sh` / `restore.sh` + DR notes |
| **WORKFLOW & DIRECTORY** | | | | |
| Transition field-gating (`requires:[field]`) | No | Partial | No | **Built** — workflow buttons disable until required fields are filled (e.g. RFI needs an answer to be Answered) |
| Company / Contact directory + reference lookups | No | view | No | **Built** (Procore-parity) — config modules + first-class `reference` lookups (e.g. `subcontract.vendor_company`) |
| Due / overdue SLA feed | No | Partial | No | **Built** (Procore-parity) — `GET /due-feed` cross-module + a "Deadlines" portal-home widget |

## Verified this round
- **Clash detection** (`services/data/.../clash.py`): bakes world geometry via the
  IfcOpenShell iterator, vectorized AABB overlap between IFC-class groups. On the structural
  sample: 2783 broad-phase candidates; 42 significant (≥0.05 m³); top = pile-cap × column
  0.477 m³. `POST /projects/{id}/clash?...&create_topics=true` turns clashes into BCF
  **clash topics** (pins/issues). Verified in UI: 30 clash topics listed alongside the RFI.
- **IDS validation** (`services/data/.../validate.py`): ifctester against an uploaded `.ids`
  or built-in default specs. On the sample: Columns-have-a-Name 203/203 pass; Slabs-declare-
  LoadBearing 0/299 fail. `POST /projects/{id}/validate`. Verified in UI: result summary +
  "Highlight 299 failures" → failing slabs highlighted green in 3D.

## Federated clash (verified)
`clash.detect_federated` bakes each discipline model, tags elements by model, and clashes
**across models only** (intra-model joints excluded). Verified: structural IFC vs an authored
services IFC (ducts routed through the frame) → 400 mesh-verified cross-discipline clashes
(beams 349, walls, columns, slabs), all cross-model. Viewer federation verified live with the
real structural + architectural discipline frags loaded together. `POST /projects/{id}/clash/federated`.

## Honest gaps (next, all open-source)
- ~~Clash narrow phase~~ ✅ done — trimesh + manifold3d boolean intersection gives exact
  penetration volume per pair; the API/UI now report `method: "mesh"`.
- ~~2D plans/sections~~ ✅ done — `drawings.py` cuts geometry with a plane → SVG (plan per
  storey at a 1.2 m cut height; X/Y sections), served at `/projects/{id}/drawings/*`.
- ~~Sheet composer~~ ✅ done — `compose()` lays out multiple views in a grid with a title
  block; renders to SVG and PDF (reportlab). `GET /drawings/sheet.{svg,pdf}`.
- ~~Dimension lines + grid bubbles~~ ✅ done — structural grid derived from IfcColumn
  positions (no IfcGrid needed); plans draw numbered/lettered grid bubbles, grid lines, and
  grid-spacing dimensions (mm). `GET /drawings/plan.svg`.
- ~~Elevations~~ ✅ done — orthographic outline views (N/S/E/W) via per-element convex-hull
  silhouettes + storey level lines. `GET /drawings/elevation.svg?direction=`.
- ~~Grid on sheet cells~~ ✅ done — composed sheet plan cells now carry grid bubbles, grid
  lines, and overall dimensions (per-cell transform via drawing primitives, SVG + PDF).
- ~~Hidden-line removal~~ ✅ done — elevations use a depth-sorted painter's algorithm
  (opaque silhouettes; nearer occludes farther) + grid bubbles + level datums.
- ~~Room tags~~ ✅ done — `space_tags()` labels each `IfcSpace` with name + net floor area at
  its centroid on plans (`rooms=True`). Verified on an authored 2-room model (Office 20 m²,
  Meeting 12 m²); applies to any model carrying `IfcSpace`.
- ~~Leaders/callouts~~ ✅ done — `element_callouts()` tags taggable elements (doors/windows by
  default, Tag→Name) at their plan centroid; `plan_drawing_svg` draws a leader line from a boxed
  label that splays radially outward from the plan centre. `plan.svg?callouts=true` + a "Plan +
  callouts" button. Verified: 27 door/window callouts on the sample house.
- ~~Grid on section/elevation sheet cells~~ ✅ done — composed-sheet cells are all annotated:
  plans (grid + dims), sections (grid + level datums), elevations (grid + levels + HLR).
- **Federation UI**: a discipline picker to load several `.frag` and toggle by model.
- **Authoring in-browser**: stays a Bonsai-bridge concern by design (GPL boundary).
