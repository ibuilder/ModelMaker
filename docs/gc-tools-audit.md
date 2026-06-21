# GC tools audit & todo (per module)

A research-backed pass over all **69 GC-portal modules** to bring each toward the field/workflow
depth of industry-standard tools (Procore / Autodesk Construction Cloud conventions). Each module
is one `services/api/modules/<key>/module.json` driving the config-driven engine (CRUD, workflow,
list/board, relations, PDF, CSV).

Sources: [Procore punch list](https://www.procore.com/project-management/punch-list) ·
[Procore observations](https://www.procore.com/quality-safety/observations) ·
[Procore daily log fields](https://support.procore.com/faq/which-fields-in-the-daily-log-tool-can-be-configured-as-required-optional-or-hidden) ·
[Procore inspections](https://support.procore.com/products/online/user-guide/project-level/inspections).

## Batch 1 — DONE (2026-06)
Enriched **51 modules (+122 fields)** with standard fields + list columns; registry loads all 69,
module CRUD/sync tests green. `list_columns` now on 53/69 (was 3). Highlights of what each got:

### Field
- **punchlist** — +priority, responsible, due_date, est. cost · cols trade/priority/due.
- **checklist** — +category, result(Pass/Fail/N/A), notes, location.
- **photo** — +location, date_taken, trade, tags(multiselect).
- **manpower_log** — +trade, workers, hours. **timesheet** — +trade, hours, date, cost_code.
- **delivery** — +supplier, PO#, received_by, date, status. **site_logistics** — +description, date, type.

### Quality
- **inspection** — +type, inspector, date, agency, spec_section (keeps NCR/deficiency rollups).
- **deficiency** — +severity, trade, due_date, corrective_action.
- **ncr** — +severity, root_cause, disposition(Use-As-Is/Rework/Repair/Reject), corrective_action, due_date.
- **test_record** — +test_type, result, date, lab, spec_section.

### Safety
- **observation** — +type(Safe/At-Risk/Hazard), severity, location, trade, corrective_action.
- **jha / pretask_plan** — +task, hazards, controls, ppe / crew_size.
- **toolbox_talk** — +topic, date, presenter, attendees. **orientation** — +worker, company, date, trainer.
- **safety_violation** — +severity(Minor/Serious/Willful), corrective_action, due_date.

### Change / Cost / Contracts
- **noc** +description/cost/days · **proposal** +amount/scope/days.
- **budget** +original/revised/committed · **direct_cost** +vendor/amount/date/type · **owner_invoice** +amount/period/status.
- **coi** +carrier/policy/coverage/expiry · **lien_waiver** +type/amount/through_date.

### Engineering / Precon / Closeout / Resources / Sustainability / BIM
- **drawing/document** +discipline/revision/status · **permit** +type/authority/number/dates/status · **meeting/action_item/issue/design_review/transmittal** standardized.
- **bid_package/bid_solicitation/bid_submission/estimate/prequalification/value_engineering** +trade/amount/status/dates.
- **as_built/asset_register/commissioning/completion_certificate/om_manual** +system/status/dates/asset attrs.
- **cost_code/equipment_rate/labor_rate/location** rate+lookup attrs · **environmental_monitoring/leed_credit/waste_diversion** +metrics/status · **coordination_issue** +discipline/priority/location.

Left intentionally lean: the **rate/lookup tables** (equipment_rate, labor_rate, material_rate,
location, cost_code) and already-rich modules (**rfi, submittal, sov, commitment, incident,
daily_report, equipment_log, production_quantity, schedule_activity, cor, pco_request, change_event,
warranty, subcontract, prime_contract**).

## Batch 2+ — remaining todos (deeper, cross-cutting)
These need engine-level or per-module workflow/relation work, not just fields:

1. **Workflow depth** — many tools still use a 2-state draft→done flow. Add real party-gated states:
   punchlist (open→ready→verified is good; add *disputed*), inspection (add *re-inspect*),
   submittal (already 6-state; add *revise & resubmit* loop), NCR (open→disposition→verify→closed),
   safety incident (reported→investigating→closed + OSHA-recordable flag).
2. **Reference wiring** (the chains that make it a system, not 69 silos):
   - deficiency/ncr/test_record → **inspection** (already rolled up; add the back-reference field).
   - punchlist → **observation** (exists) and → **room/location**.
   - lien_waiver/coi/subcontract → **commitment** (cost tie-out).
   - submittal → **spec section / drawing**; transmittal → the documents it carries.
   - daily_report → manpower_log / delivery / production_quantity (roll the day up).
3. **Rollups** — commitment ▸ invoiced/paid; bid_package ▸ low bid; inspection ▸ pass-rate;
   safety ▸ recordable count / TRIR inputs.
4. **Required-field + validation** — mark the truly-required fields per tool (engine supports
   `required`); add number/date min-max where sensible.
5. **PDF/report templates** — per-tool branded PDFs (RFI/submittal/COR have logic; extend to
   daily report, inspection, JHA, toolbox talk, incident — the field-signable forms).
6. **Templates / boilerplate** — reusable checklists & inspection templates (Procore parity).
7. **Attachments-required gates** — photos required on punch/observation/incident close.

## How to extend
Edit `services/api/modules/<key>/module.json` (field types: text, textarea, number, currency, date,
select+options, multiselect, reference{module}, rollup{source_module,source_field,op}, signature).
The engine auto-creates the table; new fields live in the JSON `data` column (no migration). Then
restart the API (registry loads on boot) — the list/form/board/PDF all update for free.
