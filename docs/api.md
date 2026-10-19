# REST API

Base URL: `/api/`. Interactive docs at `/api/docs/` (Swagger UI) and
`/api/redoc/`; raw OpenAPI 3 schema at `/api/schema/`.

## Authentication

All endpoints require authentication.

- **Token** (scripts, integrations): `Authorization: Token <key>`.
  Obtain one with `POST /api/auth/token/` (`username`, `password`) or
  `docker compose exec web python manage.py drf_create_token <username>`.
- **Session**: if you're signed in to the web UI, the browsable API and
  Swagger UI work directly.

## Endpoints

Each resource supports `GET` (list), `POST` (create), and on `/<id>/`:
`GET`, `PUT`, `PATCH`, `DELETE`.

| Resource | Path | Filters (`?field=value`) | Search (`?search=`) covers |
|---|---|---|---|
| Projects | `/api/projects/` | `project_manager` (contact ID), `status`, `project_type`, `budget_id` | name, project ID, budget ID, PM name |
| Vendors | `/api/vendors/` | — | name, contact, address |
| Purchase orders | `/api/purchase-orders/` | `status`, `vendor`, `project`, `start_date_after`, `end_date_before` | PO #, contract #, vendor, project |
| Invoices | `/api/invoices/` | `status`, `vendor`, `purchase_order`, `project`, `invoice_date_after`, `invoice_date_before` | invoice #, vendor, PO # |
| Field reports | `/api/field-reports/` | `project`, `report_date_after`, `report_date_before` | entered by, notes, project |
| Compliance units | `/api/compliance-units/` | `unit_type` | name |
| Contacts | `/api/contacts/` | `contact_type`, `has_user` (`true`/`false`), `user` (user ID) | name, title, organization, role, email |
| Documents | `/api/documents/` | `project`, `compliance_unit`, `purchase_order`, `invoice`, `document_type`, `document_date_after`, `document_date_before` | subject, organizations, project, unit, PO #, invoice # |

Planning (see [planning.md](planning.md)):

| Resource | Path | Filters | Search covers |
|---|---|---|---|
| Plans | `/api/plans/` | `status`, `project` | project, problem statement, scope |
| Objectives | `/api/objectives/` | `project`, `status` | description, success measure |
| Risks | `/api/risks/` | `project`, `status`, `category`, `score_min` | title, description, mitigation, owner |
| Stakeholders | `/api/stakeholders/` | `project`, `contact`, `influence`, `interest` | — |
| Milestones | `/api/milestones/` | `project`, `status`, `planned_date_after`, `planned_date_before` | name |
| Communication items | `/api/communication-items/` | `project`, `method`, `frequency` | purpose, audience, owner |
| Activity notes | `/api/activity-notes/` | `project`, `note_type`, `note_date_after`, `note_date_before` | title, body, author |

Budgets (see [budgets.md](budgets.md)):

| Resource | Path | Filters | Search covers |
|---|---|---|---|
| Budgets | `/api/budgets/` | `project`, `status`, `budget_year`, `project_type` | project, prepared by, notes |
| Budget line items | `/api/budget-line-items/` | `budget`, `project`, `category` | description |
| Program budget | `/api/program-budget/` (GET only) | `cycle` (fiscal year, default current), `basis` (`adopted` default, or `proposed`), `program` (a project type) | — |

A budget returns its read-only `total`, `superseded_by` and nested
`line_items`. Line items are written with their `amounts` as a list of
`{"fiscal_year": 2028, "amount": "125000.00"}` (each year once); writing
`amounts` replaces the whole list. Line items of approved, superseded or
rejected budgets can't be created, changed or deleted. Setting a budget's
`status` to `APPROVED` needs `approved_by` and `approved_date`, and supersedes
the project's previously approved budget. A project has one budget per
`budget_year`. The program budget returns `fiscal_years`, then per program its
`totals`, `categories` and `projects`, each with `prior_years`,
`fiscal_years` (`{"FY2027": "..."}`), `five_year_total`, `later_years` and
`total`.

Permit compliance (see [compliance.md](compliance.md)):

| Resource | Path | Filters | Search covers |
|---|---|---|---|
| Permits | `/api/permits/` | `compliance_unit`, `manager` (contact ID), `status`, `expiration_date_before` | name, permit #, agency, description, unit, manager |
| Compliance milestones | `/api/compliance-milestones/` | `status` (also `OVERDUE` and `OPEN`), `permit`, `compliance_unit`, `manager` (contact ID), `due_date_after`, `due_date_before`, `submittal_document` | name, condition #, description, permit name and #, manager |

A milestone's `status` is the stored progress state (`NOT_STARTED`,
`IN_PROGRESS`, `SUBMITTED`, `COMPLETE`); read-only `current_status` is
`OVERDUE` when the due date has passed and it isn't submitted or complete, and
`is_overdue` says the same as a boolean. The `status` filter matches
`current_status`: `?status=OVERDUE` finds overdue milestones, `?status=NOT_STARTED`
and `?status=IN_PROGRESS` leave them out, and `?status=OPEN` returns everything not
yet submitted or complete. `variance_days` is days submitted late (+) or early (−).
Permits and milestones are written with a `manager` contact ID (an internal
contact) and return `manager_name`. Milestone writes also need `target_date` on or before
`due_date`; a `submitted_date` (not in the future) for `SUBMITTED` and
`COMPLETE`; and a `submittal_document` filed under the permit's compliance unit.

Risk `score`, stakeholder `engagement_strategy` and milestone `variance_days`
are read-only computed fields. Stakeholders are written with a `contact` ID and
return the contact's `contact_name` and `organization`; a contact can appear
only once per project. Projects are written with a `project_manager` contact ID (an internal contact) and return
the manager's `project_manager_name`. Contacts return `username` for a linked user. A monthly note's `period` may be any date in the
month; it is stored as the 1st.

Also on every list: `?ordering=<field>` (prefix `-` for descending) and
`?page=<n>` (50 per page). List responses look like
`{"count": 123, "next": "...", "previous": null, "results": [...]}`.

Foreign keys are written and read as UUIDs; responses also include readable
companions such as `vendor_name`, `project_display` and `status_display`.

## Examples

```bash
TOKEN=...   # see above
H="Authorization: Token $TOKEN"

# Create a vendor
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/vendors/ \
  -d '{"name": "Granite Ridge Contractors", "primary_contact_name": "Kim Lo"}'

# Create a project
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/projects/ \
  -d '{"name": "Riverside Trail Extension", "project_id": "2024-3-14-0", "budget_id": "6822015",
       "project_type": "CIP_RR", "status": "CONSTRUCTION", "project_manager": "<contact uuid>"}'

# Active construction projects for one project manager
curl -H "$H" "localhost:8000/api/projects/?project_manager=<contact uuid>&status=CONSTRUCTION"

# Open POs for a project, largest first
curl -H "$H" "localhost:8000/api/purchase-orders/?project=<uuid>&status=OPEN&ordering=-amount"

# Log last month's update
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/activity-notes/ \
  -d '{"project": "<uuid>", "note_type": "MONTHLY", "period": "2026-09-01",
       "author_name": "Dana Whitfield", "body": "Activities: ..."}'

# Mark an invoice paid
curl -H "$H" -H "Content-Type: application/json" -X PATCH localhost:8000/api/invoices/<uuid>/ \
  -d '{"status": "PAID", "paid_date": "2026-10-01"}'

# Start an FY2028 budget and add construction costs for FY2028-FY2029
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/budgets/ \
  -d '{"project": "<uuid>", "budget_year": 2028, "prepared_by": "Dana Whitfield"}'
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/budget-line-items/ \
  -d '{"budget": "<uuid>", "category": "CONSTRUCTION", "description": "General contract",
       "amounts": [{"fiscal_year": 2028, "amount": "1200000.00"}, {"fiscal_year": 2029, "amount": "800000.00"}]}'

# Approve it (supersedes the previously approved budget)
curl -H "$H" -H "Content-Type: application/json" -X PATCH localhost:8000/api/budgets/<uuid>/ \
  -d '{"status": "APPROVED", "approved_by": "Board of Commissioners", "approved_date": "2027-09-15"}'

# The proposed FY2028 CIP R&R program
curl -H "$H" "localhost:8000/api/program-budget/?cycle=2028&basis=proposed&program=CIP_RR"
```

Documents need at least one of `project`, `compliance_unit`, `purchase_order`
or `invoice`. A document's file is uploaded as `multipart/form-data` on create
or update; responses give `file` (a download URL under the API, so token auth
works) and `file_name`, both `null` when there is none. Send `"file": null` to
remove it. `GET /api/documents/<id>/file/` returns the file itself (`404` if none).

```bash
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/documents/ \
  -d '{"compliance_unit": "<uuid>", "subject": "Discharge Monitoring Report — September 2026",
       "document_type": "REPORT", "document_date": "2026-10-20",
       "originating_organization": "Riverbend Water & Sewer Utility",
       "recipient_organization": "State Department of Environmental Quality"}'

# Attach (or replace) its PDF, then download it
curl -H "$H" -X PATCH -F "file=@DMR-2026-09.pdf" localhost:8000/api/documents/<uuid>/
curl -H "$H" -o DMR-2026-09.pdf localhost:8000/api/documents/<uuid>/file/
```

```bash
# Overdue compliance milestones, oldest first; then mark one submitted with its report
curl -H "$H" "localhost:8000/api/compliance-milestones/?status=OVERDUE&ordering=due_date"
curl -H "$H" -H "Content-Type: application/json" -X PATCH localhost:8000/api/compliance-milestones/<uuid>/ \
  -d '{"status": "SUBMITTED", "submitted_date": "2026-10-16", "submittal_document": "<document uuid>"}'
```

## Validation errors

Invalid writes return `400` with field-keyed messages, e.g.

```json
{"project_id": ["Project ID must look like 2021-2-20-0 (year-#-#-#)."]}
{"purchase_order": ["Purchase order belongs to a different vendor."]}
{"non_field_errors": ["Link the document to at least one project, compliance unit, purchase order or invoice."]}
```
