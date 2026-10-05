# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What this is

ProjectHub: a Django 5.2 + PostgreSQL project-management demo app, run with
Docker Compose. Public GitHub repo; **all data is fictitious** — never add real
people, organizations, budgets or contact details. See README.md for the
feature overview and docs/ for details.

## Running things

Everything runs in Docker. The `web` service bind-mounts the repo, so edits
reload automatically.

```bash
docker compose up -d --build                            # start (http://localhost:8000)
docker compose exec web python manage.py test pm planning  # tests — run after every change
docker compose exec web python manage.py makemigrations pm
docker compose exec web python manage.py migrate
docker compose logs -f web
docker compose exec web python manage.py seed_demo --flush  # reload fictitious demo data
```

Files created by `manage.py` inside the container (e.g. migrations) should be
owned by the host user: `docker compose run --rm -u "$(id -u):$(id -g)" --entrypoint python web manage.py ...`.

## Where things live

- `pm/models.py` — domain models; business rules in `clean()`.
- `pm/resources.py` — **UI registry**. List columns, search fields, related
  tables on detail pages. Most UI changes start here, not in templates.
- `pm/views.py` — dashboard + generic CRUD views. `pm/urls.py` generates URLs.
- `pm/filters.py` — FilterSets shared by UI and API.
- `pm/api/` — DRF serializers/viewsets/router. Serializers using
  `ModelCleanMixin` run model `clean()`.
- `templates/` — `base.html` (layout, Tailwind config), `pm/` generic pages.
- `pm/demo.py` — demo-data generator (fictitious water/wastewater utility);
  `pm/management/commands/seed_demo.py` wraps it. When models change, update
  the generator so `seed_demo` keeps working (covered by `pm/tests/test_seed.py`).
- `planning/` — project plans (problem statement, scope, objectives, risks,
  stakeholders, milestones, communication plan) and activity notes. Separate
  app that plugs into pm through hooks in `pm/resources.py` and `pm/demo.py`,
  registered in `planning/resources.py` / `planning/demo.py`. **pm must never
  import planning.** See docs/planning.md.
- `docs/` — data-model.md, api.md, architecture.md, planning.md.

## Conventions

- UUID primary keys via `BaseModel`. Human identifiers are separate fields.
- Put validation in model `clean()` so forms and API agree; add a test for it.
- When changing a model: update the form field list, serializer `fields`,
  FilterSet, `resources.py` entry, admin, **docs/data-model.md**, and tests.
- When adding an API filter or endpoint, update **docs/api.md**.
- New feature areas go in their own app and extend pm through its hooks
  (`register`, `register_tab`, `register_dashboard_panel`, `demo.EXTENSIONS`)
  rather than editing pm templates/views directly.
- Money is `DecimalField(max_digits=14, decimal_places=2)`; render with
  `display.money` / the `money` template filter.
- Styling: Tailwind utility classes with the custom tokens defined in
  `templates/base.html` (`primary`, `ink`, `body`, `stroke`, `boxdark`, ...).
  Every new element needs `dark:` variants.
- Match existing code style: Black-ish formatting, 120-col lines, docstrings
  on modules and non-obvious classes.
