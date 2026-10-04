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
