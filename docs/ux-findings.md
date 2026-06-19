# UX / UI findings — app-wide heuristic review

A lightweight pass across the four workspaces (Model / Drawings / Construction / Finance) and the
shared chrome, capturing issues by severity with a recommended order. Seeded from the 2026-06
tools-panel redesign; the rest is a backlog to work through, not yet implemented.

Severity: **High** (hurts daily use / blocks discovery) · **Med** (friction) · **Low** (polish).

## Done — tools & analysis surface (2026-06)
- ✅ **Two confusing tool surfaces.** Rule established: the floating viewer toolbar = *interact with
  the model*; the ⚙ Tools rail = *produce outputs / run analysis / batch edits*. Removed the
  duplicate rail "Measure" section (moved "clear" to the toolbar).
- ✅ **Everything always shown.** Tools rail is now a collapsible accordion with per-section
  preconditions; unmet → one muted "needs a project / source IFC" line + auto-collapse (no more
  repeated dead rows). Open/closed state persists.
- ✅ **Cramped results.** Cost / Energy / MEP / IDS / clash now open a readable result modal
  (`ui/result.ts`) with tables/metric grids; a one-line status stays in the rail.
- ✅ **Not role-aware.** Tools panel now persona-ordered (`TOOLS_BY_PERSONA`): a persona's primary
  tools sit on top, the rest fold under "More tools". Mirrors the existing workspace/rail filtering.
- ✅ **Construction portal scaled poorly (68 modules).** The catalog is now a collapsible,
  persona-aware section accordion (12 groups with count badges; `SECTIONS_BY_PERSONA` controls
  default-open), with ★ favorites pinned to a top group and a "Filter modules…" box that narrows and
  auto-expands matches. Open state persists; re-orders live on persona change.
- ✅ **Workspace ↔ tool overlap.** The ⚙ Tools rail now opens with a one-line note framing it as
  "model-derived analysis & exports", and the Cost section deep-links to the Construction workspace
  (where budgets/change-orders are managed) via an `aec:workspace` event — so the rail reads as a
  quick model-side surface, not a competing home.
- ✅ **Icon-only floating toolbar.** The ~20-glyph row is split into functional groups with
  separators — measure/visibility ┊ collaboration ┊ view-aids ┊ authoring (the authoring group and
  its divider hide for non-editors).

## Backlog

### Med
- **Empty-state consistency.** Different panels phrase "no project / no model / no source IFC"
  differently. Standardize copy and styling (the tools accordion's muted-reason pattern is a good
  template to reuse in the portal and drawings).
- **Result/feedback reuse.** The new `toast` + `showResult` modal pattern should be the standard for
  long-running portal actions (sync, exports, bulk ops) instead of inline text.

### Low
- **Theme/contrast audit** in light mode (the dark theme is the primary; verify the result modal,
  accordion chevrons, and disabled-state contrast in light mode).
- **Keyboard & a11y.** Accordion headers are real `<button>`s with focus (good); audit tab order and
  ensure the result modal traps/returns focus and the toolbar buttons keep their `aria-label`s.
- **Responsive / mobile** layout was not reviewed; the rail + floating toolbar likely need a
  narrow-viewport treatment.

## Not yet reviewed
- **Finance / Proforma** workspace (scenarios, sensitivity, portfolio roll-up) — needs its own pass.
- **Drawings set** workspace beyond the earlier layout fix — the sheet register / markup flow looks
  solid but deserves a task-flow review (create → markup → promote-to-RFI).
