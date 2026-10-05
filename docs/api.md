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
| Projects | `/api/projects/` | `status`, `project_type`, `budget_id` | name, project ID, budget ID, PM |
| Vendors | `/api/vendors/` | — | name, contact, address |
| Purchase orders | `/api/purchase-orders/` | `status`, `vendor`, `project`, `start_date_after`, `end_date_before` | PO #, contract #, vendor, project |
| Invoices | `/api/invoices/` | `status`, `vendor`, `purchase_order`, `project`, `invoice_date_after`, `invoice_date_before` | invoice #, vendor, PO # |
| Field reports | `/api/field-reports/` | `project`, `report_date_after`, `report_date_before` | entered by, notes, project |
| Documents | `/api/documents/` | `project`, `document_type`, `document_date_after`, `document_date_before` | subject, organizations, project |

Planning (see [planning.md](planning.md)):

| Resource | Path | Filters | Search covers |
|---|---|---|---|
| Plans | `/api/plans/` | `status`, `project` | project, problem statement, scope |
| Objectives | `/api/objectives/` | `project`, `status` | description, success measure |
| Risks | `/api/risks/` | `project`, `status`, `category`, `score_min` | title, description, mitigation, owner |
| Stakeholders | `/api/stakeholders/` | `project`, `influence`, `interest` | name, organization, role |
| Milestones | `/api/milestones/` | `project`, `status`, `planned_date_after`, `planned_date_before` | name |
| Communication items | `/api/communication-items/` | `project`, `method`, `frequency` | purpose, audience, owner |
| Activity notes | `/api/activity-notes/` | `project`, `note_type`, `note_date_after`, `note_date_before` | title, body, author |

Risk `score`, stakeholder `engagement_strategy` and milestone `variance_days`
are read-only computed fields. A monthly note's `period` may be any date in the
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
       "project_type": "CIP", "status": "CONSTRUCTION", "project_manager": "Dana Whitfield"}'

# Open POs for a project, largest first
curl -H "$H" "localhost:8000/api/purchase-orders/?project=<uuid>&status=OPEN&ordering=-amount"

# Log last month's update
curl -H "$H" -H "Content-Type: application/json" -X POST localhost:8000/api/activity-notes/ \
  -d '{"project": "<uuid>", "note_type": "MONTHLY", "period": "2026-09-01",
       "author_name": "Dana Whitfield", "body": "Activities: ..."}'

# Mark an invoice paid
curl -H "$H" -H "Content-Type: application/json" -X PATCH localhost:8000/api/invoices/<uuid>/ \
  -d '{"status": "PAID", "paid_date": "2026-10-01"}'
```

## Validation errors

Invalid writes return `400` with field-keyed messages, e.g.

```json
{"project_id": ["Project ID must look like 2021-2-20-0 (year-#-#-#)."]}
{"purchase_order": ["Purchase order belongs to a different vendor."]}
```
