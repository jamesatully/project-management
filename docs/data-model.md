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
| `project_manager` | FK → Contact | Required. Must be an **internal** contact (checked in `clean()`; the form only offers internal contacts). |

## Compliance Unit

A regulated system or permit the utility reports on, e.g. the *Northwest
Wastewater Treatment System* or the *Central Regional Potable Water System*.
Compliance records (monitoring reports, permit renewals, inspections) are
documents linked to the unit. Its permits and their compliance milestones live
in the `compliance` app — see [compliance.md](compliance.md). A unit can't be
deleted while it has permits.

| Field | Type | Notes |
|---|---|---|
| `name` | text, **unique** | Unit name. |
| `unit_type` | choice | `WATER_USE_PERMIT`, `PUBLIC_WATER_SUPPLY`, `WASTEWATER`, `TANK`, `STORMWATER`, `OTHER` |

## Contact

The shared address book: people (and groups such as a board or neighborhood
association) the utility works with, internal or external. Planning
stakeholders reference contacts, so a person is entered once and reused across
projects. Project managers are contacts too. Some contacts are app users; most aren't.

| Field | Type | Notes |
|---|---|---|
| `name` | text | Full name, or a group's name. Not unique (people share names). |
| `title` | text | Job title. optional |
| `organization` | text | optional |
| `contact_type` | choice | `INTERNAL` (works for the utility) or `EXTERNAL` (default) |
| `role_description` | long text | Their role in their organization. optional |
| `email` | email | optional |
| `phone` | text | optional |
| `user` | one-to-one → User | optional. Each user account links to at most one contact. Deleting the user keeps the contact (link cleared). |

A contact can't be deleted while it manages a project, permit or compliance milestone, or is a stakeholder on any project. A contact's page lists
the projects they manage.

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
documents reference them, and a document can't be deleted while it's a
compliance milestone's submittal ([compliance.md](compliance.md)).

A document can carry **one uploaded file** (mostly PDFs). Allowed types: PDF,
Word (`doc`/`docx`), Excel (`xls`/`xlsx`/`csv`), PowerPoint (`ppt`/`pptx`),
OpenDocument (`odt`/`ods`/`odp`), `rtf`, `txt`, Outlook/email (`msg`/`eml`) and
images (`png`/`jpg`/`jpeg`/`tif`/`tiff`), up to 50 MB. Files are stored under
`MEDIA_ROOT/documents/<document id>/` (default `./media`, git-ignored) and are
**not** publicly served: `/documents/<id>/file/` returns the file to logged-in
users, inline, so PDFs, images and text open in the browser tab and other types
download. Replacing or removing a file, or deleting its document, deletes the
old file from storage.

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
| `file` | file | optional; see allowed types above. |
| `added_date` | datetime | Set automatically on creation. |
| `last_edited_date` | datetime | Updated automatically on every save. |

## Change history

- **Project types** changed from CIP / Development / Environmental to
  CIP Expansion / CIP R&R / Development. Migration `pm.0002` converts existing
  CIP and Environmental projects to CIP R&R; reclassify expansion projects as
  needed (rolling back converts both CIP types back to CIP).
- **Compliance units** added; **documents** can link to projects, compliance
  units, purchase orders and invoices (previously projects only).
- **Contacts** added. Planning stakeholders now link to a contact instead of
  storing name / organization / contact details themselves. Migrations
  `planning.0002`–`0003` create one contact per distinct name + organization
  (as *External*; mark utility staff *Internal* afterwards) and keep the first
  phone or email seen. Rolling back copies the details back onto stakeholders.
- **Permits and compliance milestones** added in the `compliance` app
  ([compliance.md](compliance.md)); new tables only, no changes to pm tables.
- **Document files**: `Document.file` added (migration `pm.0007`, optional, so
  existing documents are unaffected).

## Additions beyond the original spec

These were added so the dashboard can report spend per project. Remove them
if they don't fit the target enterprise model:

- `PurchaseOrder.project` (optional FK) — links commitments to a project.
- `Invoice.amount` — needed for invoiced/paid totals.
- `Contact.contact_type`, `email`, `phone` — internal/external filtering, and a
  home for the contact details stakeholders used to carry.

Status and document-type choice lists were also chosen for this demo and are
easy to change in `pm/models.py` (then run `makemigrations`).
