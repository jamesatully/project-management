# Project planning

The `planning` app adds project plans and progress notes on top of the core
`pm` records. It lives in its own Django app so it can be evaluated, changed or
removed independently; `pm` never imports it.

## What's in a plan

| Section | Model | Notes |
|---|---|---|
| Problem statement, scope | `ProjectPlan` | One per project. *In scope* and *Out of scope* are separate fields so exclusions are explicit. Status: Draft → In Review → Approved (approval needs an approver name and date). |
| Objectives | `Objective` | Description, success measure, target date, status (Not Started / On Track / At Risk / Achieved / Not Achieved), display order. |
| Risk register | `Risk` | Title, category, likelihood (1–5) × impact (1–5) = **score** (1–25, computed), owner, mitigation, status (Open / Mitigating / Closed), identified and next-review dates. Scores ≥ 15 are *High*, 8–14 *Medium*, < 8 *Low*. |
| Stakeholders | `Stakeholder` | Name, organization, role, influence and interest (High/Medium/Low), contact, engagement notes. The **engagement strategy** (Manage closely / Keep satisfied / Keep informed / Monitor) is derived from the influence–interest grid. |
| Milestones | `Milestone` | Planned (baseline), forecast and actual dates; **variance** in days is derived; status (Not Started / In Progress / At Risk / Complete / Missed). Complete milestones need an actual date. |
| Communication plan | `CommunicationItem` | What, audience, method, frequency, owner, notes. |
| Activity notes | `ActivityNote` | Monthly update, decision, issue or general note; author (free text), date, optional title, body. Monthly updates carry a reporting month and are limited to **one per project per month**. |

Section records belong to the project (not the plan record), so they can be
listed and filtered across the whole portfolio — e.g. *all open risks scoring
15+*. Deleting a project deletes its plan, sections and notes.

## Where it appears in the app

- **Project page tabs** — *Overview* (existing details), *Plan* (narrative plus
  a table per section, each with Add/Edit), *Activity* (timeline of notes with
  a type filter and a prompt when last month's update is missing).
- **Sidebar → Planning** — portfolio-wide lists of Project Plans, Risks,
  Milestones and Activity Notes, with the usual search, filters and sorting.
- **Dashboard** — *Monthly updates due* (active projects in Design or
  Construction with no update for the previous month, each with a one-click
  "Add update") and *Top open risks*.

"Add update" opens the note form pre-filled with the project, the previous
month and the project manager's name; saving returns you to where you started.

## API

`/api/plans/`, `/api/objectives/`, `/api/risks/`, `/api/stakeholders/`,
`/api/milestones/`, `/api/communication-items/`, `/api/activity-notes/` — see
[api.md](api.md).

## How it plugs into `pm`

`planning/apps.py` imports `planning/resources.py` and `planning/demo.py` at
startup. These call `pm`'s extension points:

| Hook | Used for |
|---|---|
| `pm.resources.register(Resource(...))` | Generic list/detail/create/edit/delete pages for each planning model, and sidebar entries (`nav_group="Planning"`). |
| `pm.resources.register_tab("project", Tab(...))` | The Plan and Activity tabs on project pages. |
| `pm.resources.register_dashboard_panel(fn)` | The two dashboard panels. |
| `pm.demo.EXTENSIONS.append(fn)` | Planning demo data created by `seed_demo`. |

Generic form pages accept `?<field>=<value>` to pre-fill fields and
`?next=<local url>` to return somewhere specific after saving or deleting.

## Ideas not built yet

- Plan versioning / approved snapshots and a baseline-vs-current comparison.
- Linking communication-plan audiences to stakeholder records.
- Notes authored by logged-in users (currently a free-text name).
- Risk heat map (likelihood × impact grid) and milestone timeline views.
- Exporting a plan as a document.
