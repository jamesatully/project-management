# Permit compliance

The `compliance` app tracks the permits each compliance unit operates under and
the milestones those permits require: reports, submittals and other actions
with a regulatory due date, such as a drinking water system's monthly operating
report. It lives in its own Django app and plugs into `pm` the same way
`planning` and `budgets` do; `pm` never imports it.

```
pm.ComplianceUnit ──< Permit ──< ComplianceMilestone ──> pm.Contact (milestone manager)
                        │                └──> pm.Document (submittal, optional)
                        └──> pm.Contact (permit manager)
```

## Permits

| Field | Type | Notes |
|---|---|---|
| `compliance_unit` | FK → Compliance Unit | Required. A unit can't be deleted while it has permits. |
| `name` | text | Permit name, e.g. *Riverbend WWTP NPDES Permit*. |
| `permit_number` | text | Agency-assigned number. optional; not unique (renewals often keep the number). |
| `issuing_agency` | text | |
| `manager` | FK → Contact | *Permit manager*: responsible for the permit overall. Required; must be an **internal** contact. A contact can't be deleted while managing permits. |
| `status` | choice | `PENDING` (Application Pending), `ACTIVE` (default), `EXTENDED` (Administratively Extended — expired, renewal under review), `EXPIRED`, `TERMINATED` |
| `effective_date`, `expiration_date` | date | optional; expiration can't precede the effective date |
| `description` | long text | optional |

The permit list shows each permit's **next due** date (its earliest open milestone).

The permit manager and each milestone's manager are often different people:
the permit manager owns the permit as a whole, while milestone managers run
individual deliverables. Both are planned recipients of pending-milestone
notifications (see *Ideas not built yet*).

## Compliance milestones

| Field | Type | Notes |
|---|---|---|
| `permit` | FK → Permit | Required. Milestones are deleted with their permit. |
| `manager` | FK → Contact | *Milestone manager.* Must be an **internal** contact. A contact can't be deleted while managing milestones. |
| `name` | text | *Milestone name*, e.g. *Monthly Operating Report — September 2026*. |
| `permit_condition` | text | *Permit condition #*, e.g. `S1.A`. |
| `due_date` | date | Regulatory deadline. |
| `target_date` | date | *Internal target date.* optional; must be on or before the due date. |
| `status` | choice | `NOT_STARTED` (default), `IN_PROGRESS`, `SUBMITTED`, `COMPLETE` |
| `submitted_date` | date | *Date submitted / completed.* Required for Submitted and Complete; can't be in the future. |
| `submittal_document` | FK → Document | optional. Must be a document filed under the permit's compliance unit. A document can't be deleted while it's a milestone's submittal. |
| `description` | long text | optional |

**Overdue is derived, not stored.** A milestone is *overdue* when its due date
has passed and its status is still Not Started or In Progress. The app shows
"Overdue" in place of the stored status (lists, detail page, dashboard), and the
status filter works on what's shown: *Overdue* finds those milestones, and
*Not Started* / *In Progress* exclude them. *Open* finds everything not yet
submitted or complete. Storing it would need a nightly job to keep it current,
and a status someone forgot to update would hide a missed deadline.

**Submitted vs. due** (detail page and API `variance_days`) shows how many days
early or late a milestone was submitted.

**Recurring requirements** are entered as one milestone per occurrence — each
monthly report is its own milestone with its own due date, status and
submittal — so the history shows exactly what was submitted when.

Default order: open milestones first, soonest due at the top (so overdue ones
lead), then submitted and complete ones, most recent first. Column headers
re-sort as usual.

## Where it appears in the app

- **Sidebar → Compliance** — *Permits* and *Compliance Milestones*, with search,
  filters (status, permit, compliance unit, milestone manager, due date range)
  and sorting.
- **Compliance unit pages** list the unit's permits; **permit pages** list its
  milestones with an *Add* button that pre-fills the permit.
- **Contact pages** list the permits and milestones a person manages; **document pages**
  list the milestones the document is the submittal for.
- **Dashboard → Compliance deadlines** — overdue milestones and those due in the
  next 30 days, soonest first, with links to the overdue and open lists.
- The milestone form's document dropdown lists only documents filed under a
  compliance unit — just the chosen permit's unit when the permit is known.

## API

`/api/permits/` and `/api/compliance-milestones/` — see [api.md](api.md).

## How it plugs into `pm`

`compliance/apps.py` imports `compliance/resources.py` and `compliance/demo.py` at startup:

| Hook | Used for |
|---|---|
| `pm.resources.register(Resource(...))` | Permit and milestone pages and the *Compliance* sidebar group. The milestone detail page lists the derived status and submitted-vs-due days through `Column` entries in `detail_fields`. |
| `pm.resources.register_related(...)` | Permits on compliance unit pages; milestones on contact and document pages. |
| `pm.resources.register_dashboard_panel(fn)` | The *Compliance deadlines* panel. |
| `pm.demo.EXTENSIONS.append(fn)` | Demo permits, milestones and compliance staff. |
| `pm.demo.FLUSH_FIRST` | `seed_demo --flush` deletes milestones and permits before pm's records, since they protect documents, contacts and compliance units. |

## Demo data

Every compliance unit gets its permit (NPDES permits for the treatment plants,
operating permits for the water systems, water use permits, stormwater
coverage, biosolids and recycled water permits, tank registrations). Each
permit gets milestones for its recurring reports from January two years back to
a few months ahead, a renewal application where the permit expires, and a few
one-off items. Where pm's generator already filed the matching report under the
unit (e.g. *Discharge Monitoring Report — May 2026*), that document is the
submittal and its date the submitted date. Most past milestones were submitted
on time, a few late, and a couple are left overdue. Six internal compliance
staff are added to the contact directory as permit and milestone managers: the
regulatory compliance manager holds the treatment plant and water system
permits, specialists hold the rest. It uses its own
random stream, so other demo data doesn't change.

## Ideas not built yet

- Generating a year of occurrences from a recurring requirement (frequency +
  due-day rule) instead of entering each one.
- A compliance calendar view, and a *Milestones* tab on compliance unit pages.
- Notifications of pending milestones to both the permit manager and the
  milestone manager as target and due dates approach.
- Permit renewal tracking that links the new permit to the one it replaces.
