# Data model

Source of truth: [`pm/models.py`](../pm/models.py). Every model inherits
`BaseModel`: `id` (UUID, primary key), `created_at`, `updated_at`.

## Project

| Field | Type | Notes |
|---|---|---|
| `name` | text | |
| `project_id` | text, **unique** | Manually entered. Must match `YYYY-#-#-#`, e.g. `2021-2-20-0`. |
| `budget_id` | text | Digits only, e.g. `6822015`. Not unique — several projects may share a budget. Indexed. |
| `project_type` | choice | `CIP_EXPANSION` (CIP Expansion — new capacity or treatment), `CIP_RR` (CIP R&R — renewal and replacement), `DEVELOPMENT` |
| `status` | choice | `PLANNING` (default), `DESIGN`, `CONSTRUCTION`, `ON_HOLD`, `COMPLETE`, `CANCELLED` |
| `project_manager` | text | Name. |

## Compliance Unit

A regulated system or permit the utility reports on, e.g. the *Northwest
Wastewater Treatment System* or the *Central Regional Potable Water System*.
Compliance records (monitoring reports, permit renewals, inspections) are
documents linked to the unit.

| Field | Type | Notes |
|---|---|---|
| `name` | text, **unique** | Unit name. |
| `unit_type` | choice | `WATER_USE_PERMIT`, `PUBLIC_WATER_SUPPLY`, `WASTEWATER`, `TANK`, `STORMWATER`, `OTHER` |

## Vendor

| Field | Type | Notes |
|---|---|---|
| `name` | text, **unique** | |
| `mailing_address` | long text | optional |
| `website` | URL | optional |
| `primary_contact_name` | text | optional |
| `primary_contact_phone` | text | optional |

## Purchase Order

| Field | Type | Notes |
|---|---|---|
| `po_number` | text, **unique** | |
| `status` | choice | `DRAFT` (default), `OPEN`, `CLOSED`, `CANCELLED` |
| `amount` | decimal(14,2) | ≥ 0 |
| `vendor` | FK → Vendor | required; vendor can't be deleted while it has POs |
| `project` | FK → Project | **optional** (addition to the original spec, see below) |
| `contract_number` | text | optional |
| `start_date`, `end_date` | date | optional; end can't precede start |

## Invoice

| Field | Type | Notes |
|---|---|---|
| `invoice_number` | text | User/vendor defined. Unique **per vendor**. |
| `vendor` | FK → Vendor | Must equal the purchase order's vendor. |
| `status` | choice | `RECEIVED` (default), `UNDER_REVIEW`, `APPROVED`, `PAID`, `REJECTED` |
| `purchase_order` | FK → Purchase Order | required |
| `amount` | decimal(14,2) | ≥ 0 (addition to the original spec, see below) |
| `invoice_date` | date | required |
| `received_date`, `paid_date` | date | optional; `paid_date` required when status is `PAID` |

## Field Report

| Field | Type | Notes |
|---|---|---|
| `project` | FK → Project | deleting a project deletes its field reports |
| `entered_by` | text | Name. |
| `report_date` | date | Date of the site visit. |
| `data_entry_date` | date | Defaults to today. |
| `time_on_site` | decimal(5,2) | Hours. |
| `observation_notes`, `safety_notes`, `weather_notes` | long text | optional |

## Document

A document links to **any combination** of a project, compliance unit,
purchase order and invoice, and must link to **at least one** (enforced in
forms, the API and a database check constraint). For example, a returned-invoice
letter links to the invoice, its PO and the project; a discharge monitoring
report links only to its compliance unit. Linked records can't be deleted while
documents reference them.

| Field | Type | Notes |
|---|---|---|
| `project` | FK → Project | optional |
| `compliance_unit` | FK → Compliance Unit | optional |
| `purchase_order` | FK → Purchase Order | optional |
| `invoice` | FK → Invoice | optional |
| `subject` | text | |
| `originating_organization`, `recipient_organization` | text | |
| `document_type` | choice | `LETTER`, `MEMO`, `EMAIL`, `RFI`, `SUBMITTAL`, `CHANGE_ORDER`, `MEETING_MINUTES`, `REPORT`, `DRAWING`, `OTHER` |
| `document_date` | date | Date on the document. |
| `added_date` | datetime | Set automatically on creation. |
| `last_edited_date` | datetime | Updated automatically on every save. |

## Change history

- **Project types** changed from CIP / Development / Environmental to
  CIP Expansion / CIP R&R / Development. Migration `pm.0002` converts existing
  CIP and Environmental projects to CIP R&R; reclassify expansion projects as
  needed (rolling back converts both CIP types back to CIP).
- **Compliance units** added; **documents** can link to projects, compliance
  units, purchase orders and invoices (previously projects only).

## Additions beyond the original spec

These were added so the dashboard can report spend per project. Remove them
if they don't fit the target enterprise model:

- `PurchaseOrder.project` (optional FK) — links commitments to a project.
- `Invoice.amount` — needed for invoiced/paid totals.

Status and document-type choice lists were also chosen for this demo and are
easy to change in `pm/models.py` (then run `makemigrations`).
