# Architecture

## Layout

```
config/            Django project: settings (env-driven), root URLs, WSGI/ASGI
pm/                The single Django app
  models.py        Domain models (see data-model.md)
  filters.py       django-filter FilterSets — shared by API and web UI
  forms.py         ModelForms with Tailwind styling
  resources.py     UI registry: columns, search fields, related tables per model
  views.py         Dashboard + 5 generic CRUD views driven by resources.py
  urls.py          Generates list/new/detail/edit/delete URLs per resource
  display.py       Value → HTML rendering (money, dates, status badges, links)
  api/             DRF serializers, viewsets, router
  tests/           Model, API and view tests
templates/         base layout, dashboard, generic resource pages, login
docs/              This documentation
```

## Design choices

- **One generic CRUD stack.** Rather than six hand-written sets of views and
  templates, `pm/resources.py` declares how each model is presented and the
  generic views render from it. To add a column, edit the resource's `columns`;
  to add a model to the UI, add a form, a FilterSet and a `Resource` entry
  (plus a URL prefix in `pm/urls.py` and a sidebar slot in
  `pm/context_processors.py`).
- **Validation lives on the model** (`clean()`), so forms and the API
  (`ModelCleanMixin` in `pm/api/serializers.py`) enforce identical rules.
- **Shared FilterSets** keep `?status=OPEN` meaning the same thing in the UI
  and the API.
- **`PROTECT` on financial FKs.** Vendors and purchase orders can't be deleted
  while invoices or POs reference them; the UI shows a friendly message.
  Field reports and documents cascade with their project.
- **UUID primary keys** everywhere; human identifiers (project ID, PO number,
  invoice number) are separate, user-editable fields.

## Front end

Server-rendered Django templates styled with Tailwind CSS in a TailAdmin-style
dashboard layout, Alpine.js for small interactions (sidebar, dark mode,
dropdowns), and inline Heroicons. Tailwind is loaded from its Play CDN so local
development needs no Node toolchain.

## Path to hosting

Before running this as a public hosted app:

1. **Tailwind build.** Replace the Play CDN with a compiled stylesheet (the
   Tailwind standalone CLI in a Docker build stage, scanning `templates/` and
   `pm/`) and serve it through WhiteNoise.
2. **Settings.** Set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`. Secure cookies and
   proxy-SSL handling switch on automatically when `DEBUG` is off.
3. **Server.** The image's default command is Gunicorn; the local compose
   file overrides it with `runserver`. A production compose/platform config
   should use the image default and drop the source bind-mount.
4. **Database.** Point `POSTGRES_*` at a managed PostgreSQL instance and back it up.
5. **Demo access.** Decide whether visitors get a shared read-only demo
   account or self-signup; the API currently requires authentication for all
   access.
