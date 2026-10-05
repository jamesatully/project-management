# ProjectHub — Project Management Demo

A Django dashboard for tracking capital, development and environmental projects
together with their vendors, purchase orders, invoices, field reports and
documents. Every record is also available through a documented REST API.

> **Demo data only.** All project names, people, vendors, budgets and invoices
> in this app are fictitious. It exists to prototype components and features for
> brainstorming and possible adoption into enterprise project-management tools.

## Features

- **Dashboard**: KPI tiles, invoiced-vs-committed meters per project, projects
  by status/type, invoices awaiting payment, recent field reports and documents.
- **List / detail / create / edit / delete** pages for every record type, with
  search, filters, sortable columns and pagination.
- **Related records on detail pages**: a project shows its POs, field reports and
  documents; a vendor shows its POs and invoices; a PO shows its invoices.
- **REST API** for all data, with interactive docs (Swagger UI and ReDoc) and an
  OpenAPI schema.
- **Business rules** enforced the same way in forms and the API (e.g. an invoice's
  vendor must match its purchase order's vendor; paid invoices need a paid date).
- **Project planning** (`planning` app): a plan per project — problem
  statement, in/out of scope, objectives, risk register, stakeholders,
  milestones and communication plan — plus monthly updates and other activity
  notes. Portfolio-wide risk and milestone lists; dashboard panels for overdue
  monthly updates and top risks. See [docs/planning.md](docs/planning.md).
- UUID primary keys, PostgreSQL, Docker, light/dark mode, responsive layout.

## Quick start

Requires Docker with Compose v2.

```bash
git clone https://github.com/jamesatully/project-management.git
cd project-management
cp .env.example .env                 # optional; defaults work for local use
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Open <http://localhost:8000> and sign in.

### Demo data

Load a fictitious water/wastewater utility dataset — about 100 projects (water
mains, sewer rehab, treatment plant upgrades, reservoirs, studies,
environmental and developer projects), 10 project managers, 50 vendors, 17 compliance units
(treatment systems, water use permits, tanks, stormwater programs), ~250
purchase orders, several thousand monthly invoices, project field reports and
correspondence, and a plan for nearly every project with objectives, risks,
stakeholders, milestones, a communication plan and monthly updates:

```bash
docker compose exec web python manage.py seed_demo           # into an empty database
docker compose exec web python manage.py seed_demo --flush   # replace existing data
```

Options: `--seed N` (different but reproducible dataset), `--projects N`,
`--today YYYY-MM-DD` (reference date for statuses and history). All names,
companies, addresses (`.example` domains, 555-01xx numbers) and amounts are
invented; the generator lives in [`pm/demo.py`](pm/demo.py).

| URL | What |
|---|---|
| `/` | Dashboard |
| `/projects/`, `/compliance-units/`, `/vendors/`, `/purchase-orders/`, `/invoices/`, `/field-reports/`, `/documents/` | Data pages |
| `/projects/<id>/plan/`, `/projects/<id>/activity/` | A project's plan and activity notes |
| `/plans/`, `/risks/`, `/milestones/`, `/activity/` | Planning lists across all projects |
| `/api/` | Browsable REST API |
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/admin/` | Django admin |

## Data model

```
Vendor ──< PurchaseOrder ──< Invoice
                │
Project ──< (optional) PurchaseOrder
   └──< FieldReport

Document ──> Project, Compliance Unit, Purchase Order, Invoice   (any combination, at least one)
```

| Model | Key fields |
|---|---|
| **Project** | name, project ID (unique, e.g. `2021-2-20-0`), budget ID (e.g. `6822015`, may repeat), type (CIP Expansion / CIP R&R / Development), status, project manager |
| **Compliance Unit** | unit name (e.g. *Northwest Wastewater Treatment System*), unit type (Water Use Permit / Public Water Supply / Wastewater / Tank / Stormwater / Other) |
| **Vendor** | name, mailing address, website, primary contact name and phone |
| **Purchase Order** | PO number, status, amount, vendor, project *(optional)*, contract number, start/end dates |
| **Invoice** | invoice number (unique per vendor), vendor, purchase order, status, amount, invoice/received/paid dates |
| **Field Report** | project, entered by, report date, data entry date, hours on site, observation/safety/weather notes |
| **Document** | links to a project, compliance unit, PO and/or invoice; subject, originating and recipient organizations, type, document date, added and last-edited timestamps |

All models use UUID primary keys and carry `created_at` / `updated_at`.
Full field reference: [docs/data-model.md](docs/data-model.md). Planning models
(plans, objectives, risks, stakeholders, milestones, communication items,
activity notes) are described in [docs/planning.md](docs/planning.md).

## API

```bash
# Get a token (or create one: docker compose exec web python manage.py drf_create_token <user>)
curl -X POST localhost:8000/api/auth/token/ -d username=admin -d password=...

curl -H "Authorization: Token <key>" "localhost:8000/api/projects/?status=CONSTRUCTION&search=trail"
```

See [docs/api.md](docs/api.md) for endpoints, filters and examples.

## Development

```bash
docker compose exec web python manage.py test pm planning  # run tests
docker compose exec web python manage.py makemigrations # after model changes
docker compose logs -f web                              # server logs
```

The local compose file runs Django's dev server with the source mounted, so code
changes reload automatically. Architecture notes and the hosting plan are in
[docs/architecture.md](docs/architecture.md).

## Tech stack

Django 5.2 LTS · Django REST Framework · drf-spectacular · django-filter ·
PostgreSQL 17 · Tailwind CSS (TailAdmin-style layout) · Alpine.js · Heroicons ·
Gunicorn · WhiteNoise · Docker

## License

MIT — see [LICENSE](LICENSE).
