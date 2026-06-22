# Full-lifecycle roadmap — concrete residential tower, acquisition → turnover

This doc is the output of an end-to-end drive (`services/api/e2e_tower.py`) that takes one project —
a concrete-superstructure residential tower ("Maple Street Tower") — through **every** phase of the
platform and records what works and what's missing. It's both a regression harness and the punch
list for finishing the start-to-finish story.

Run it against a live API: `python services/api/e2e_tower.py`. It prints PASS/FAIL per step and the
final source-IFC path; the deliverable model is saved to `samples/maple_tower.ifc`.

## What works today (verified end-to-end)
The whole chain runs green — one project, one GUID-stable IFC, from a zoning envelope to a completion
certificate:

| Phase | Proven in the E2E |
|---|---|
| **0 · Acquisition / feasibility** | Zoning envelope → generative massing → **IFC model** (8 floors, 55 units) + acquisition **proforma** scenario (S&U, IRR, waterfall). |
| **1 · Design** | Authored a real **concrete superstructure** onto the massing — 12 columns, 12 beams, 3 core shear walls — plus a **unit fit-out** (fridge/range/dishwasher/sink + sofa/table/bed), concrete material tag, published (reconvert + reindex). Metre-scale, GUID-stable, renders in the viewer. |
| **2 · Preconstruction** | Model **takeoff → estimate**, **cost codes + budget + commitments**, **bid package → submissions → leveling → award**, **CPM schedule** (critical path). |
| **3 · Construction** | **RFI** (submit→respond), **submittal**, full **change chain** (change event → PCO → COR submit→approve→execute), **daily report + manpower**, **inspection** (fail → NCR), **safety incident**, **SOV → G703/G702 pay app**, dashboard, AI ask. |
| **4 · Turnover / closeout** | **Punchlist** (open→ready→**evidence-gated** verify), **commissioning** (test→accept), **O&M manual**, **warranty**, **as-built**, **asset register**, **completion certificate** (issue→accept), **COBie / QTO / space-schedule** exports, **status report PDF**. |

## Bugs fixed while driving it
- **Authoring path-length blow-up (Windows).** Each `/edit` derived the new IFC filename from the
  *previous* versioned name, so chained edits compounded the stem (`source_<ts>_<ts>_…ifc`) until it
  passed the 260-char limit and the write failed. Now each version is named off the original stem +
  a microsecond stamp. *(This blocked any multi-edit authoring session — the single most important
  fix here.)*
- **web-ifc invisibility across all authoring recipes.** `IfcRectangleProfileDef` was created without
  a `Position`; ifcopenshell tolerates that but web-ifc silently skips the element, so authored
  walls/columns/beams/openings rendered invisible. Centralized a `_rect_profile()` helper that always
  sets the placement (same fix already applied to massing + families).
- (Earlier in the session: massing built in millimetres → 1000× too small; demo seed aborting on
  missing required fields.)

## Gaps to build out (prioritized) — to finish "start to finish for real"

### A. Design / modeling depth (biggest gap)
The generated model is **massing-grade** (floor-plate spaces + slabs) plus whatever you author by
hand. To carry a *real* tower to turnover it needs to be generated, not hand-placed:
1. ✅ **DONE — Generative structural framing.** `generate_ifc(frame=True, bay=…)` auto-frames every
   floor on a ~bay-metre column grid: columns at each grid intersection + beams along both axes,
   GUID-stable and metre-scale. Exposed via the generate endpoint (`frame`, `bay_m`) and a
   "Generate concrete structural frame" checkbox in the massing form — massing → structural model in
   one click. Verified (test_massing: 175 columns + 290 beams on a 7×5 grid) and visually (a framed
   tower renders columns/beams/slabs across all floors). *Next: size members from spans, two-way
   slab bands, and a proper core (stairs/elevator shafts) instead of a single shear wall.*
2. ✅ **DONE — Unit-layout generator.** `generate_ifc(units=True)` subdivides each floor into the
   proforma's per-floor unit count — a grid of per-apartment `IfcSpace`s, each with a real
   `Qto_SpaceBaseQuantities.NetFloorArea` and `Pset_SpaceCommon.Reference="UNIT"`, so areas / COBie /
   rent are grounded in actual apartments instead of one plate-sized space. Endpoint `units` flag +
   a "Subdivide floors into units" checkbox. Verified (test_massing: 65 unit spaces, 13/floor × 5
   floors, each with area). *Next: a real double-loaded corridor + core carve-out, and a unit-mix
   (studio/1BR/2BR) instead of uniform cells.*
3. ✅ **DONE — Envelope.** `generate_ifc(envelope=True, wwr=…)` wraps each floor in perimeter
   facade `IfcWall`s (IsExternal) + ribbon `IfcWindow`s at the window-to-wall ratio. The energy model
   reads the real exterior-wall + glazing areas (UA, EUI, WWR) and elevations show an enclosure.
   Endpoint `envelope`/`wwr` + a "Wrap in facade + windows" checkbox. Verified (test_massing: 20
   walls + 20 windows; energy WWR 0.36, UA 6318 W/K) and visually (the developed tower renders facade
   + ribbon windows). *Next: real curtain-wall mullions, punched vs. ribbon options, spandrel/shading.*
4. **Core & MEP stubs** — stairs, elevator shafts, risers, and major equipment (`IfcSpace` zones +
   placeholder `IfcFlowTerminal`/`IfcDistributionElement`) so coordination/clash has something to do.

### B. Estimating realism
- Model-based estimate returns a tiny number on a massing model (sparse quantities). Until (A) lands,
  **fall back to the proforma hard-cost / $-per-sf** when the model has < N structural elements, and
  surface *which* source was used. Longer-term: **assembly-based estimating** (concrete m³ × $/m³,
  formwork m², rebar tonnes) off the structural model from (A1).

### C. Construction depth
- **Multi-period pay apps** — G702/G703 across draws (period N, retainage release), and **lien
  waivers** auto-generated per pay app.
- **Logs to PDF** — RFI log, submittal log, and the change-order log as printable registers.
- **Field/mobile capture** — photo → daily report / punchlist with offline support (the Capacitor
  scaffold exists). This is where GC adoption is won.

### D. Turnover completeness
- **COBie should include the asset register + commissioning + warranty data**, not just spaces — the
  closeout modules already capture it; wire it into the COBie export.
- **Final completion package** — one ZIP: as-builts (IFC + drawings), O&M manuals, warranties, asset
  register, completion certificate, final pay app.
- **Warranty tracking** — start/expiry dates + reminders.

### E. Cross-cutting consistency
- **Module title-field inconsistency.** Modules use different required title fields — `subject`
  (rfi/cor), `title` (submittal/as_built), `name` (om_manual/warranty/asset_register), `number`
  (as_built), `system` (commissioning). Standardize on a primary title field (or add an alias the
  create endpoint accepts) so integrations/scripts don't have to special-case each module.
- **Safety TRIR/DART** reads as `None` until man-hours exist — auto-derive hours from timesheets +
  manpower logs so the metric populates without separate entry.

## The artifact
The end-to-end run saves the final model to **`samples/maple_tower.ifc`** — IFC4, metre-scale,
GUID-stable: site → building → 8 storeys, each with a floor-plate space + slab; 12 concrete columns,
12 beams and 3 core walls across the framed floors; and a Level-1 unit fit-out (appliances, sanitary,
furniture). It opens in the viewer and round-trips through the converter to Fragments.
