# Budgets

The `budgets` app holds annual project budgets and rolls them up into the
capital program (CIP Expansion, CIP R&R and Development). Like `planning`, it's
a separate Django app that plugs into `pm` through hooks; `pm` never imports it.

## Fiscal years and budget cycles

The utility's fiscal year runs **October 1 – September 30** and is named for
the calendar year it ends in: FY2027 is Oct 1, 2026 – Sep 30, 2027.

Each year the budget for the *next* fiscal year is prepared. That year is the
**budget cycle**: in October 2026 (FY2027) staff start drafting the FY2028
budget, and the Board approves it before FY2028 begins.

## Versions and statuses

A project has one **budget version per budget cycle**. Each version holds its
own line items, so earlier versions stay as a record of what was approved.

| Status | Meaning |
|---|---|
| Draft | Being prepared. Line items can be edited. |
| Submitted | Sent for review. Line items can still be edited. Submitting fills in the submitted date if it's blank. |
| Approved | Adopted. Needs an approver and an approval date. **Approving a version supersedes the project's previously approved version**, so a project has at most one approved budget at a time. |
| Superseded | Replaced by a later approved version (set automatically; links to the version that replaced it). |
| Rejected | Not adopted. Ignored by the roll-up, which falls back to the project's last approved budget. |

Approved, superseded and rejected budgets are **locked**: their line items and
amounts can't change in the UI or the API. To revise one, start a new version.
An older cycle can't be approved over a newer approved one.

Example: a project started in FY2024 has an approved FY2024 budget. In early
2025 an FY2026 draft is started, submitted in spring and approved in
September 2025. The FY2024 version then becomes *Superseded*.

## Line items and amounts

| Model | Fields |
|---|---|
| `Budget` | project, budget cycle (FY), status, prepared by, submitted date, approved by, approved date, superseded by *(automatic)*, notes |
| `BudgetLineItem` | budget, category, description *(optional)* |
| `BudgetAmount` | line item, fiscal year, amount (≥ 0); one amount per line item per fiscal year |

Categories: **Design**, **Construction**, **Land / Easement Acquisition**,
**Operating Costs to be Capitalized**. A budget can have several line items in
the same category (for example *Construction — general contract* and
*Construction — owner-furnished equipment*); the description tells them apart.

Amounts can be entered for any fiscal year, including years before the budget
cycle (costs already incurred) and years well after it.

Deleting a project deletes its budgets. Deleting a budget deletes its line
items and amounts.

## Where it appears in the app

- **Project page → Budget tab**: the approved version (or pick any version
  from the version list), shown as a grid of line items by fiscal year with
  category and column totals, plus the version history with the change in
  total from the previous version. Buttons:
  - *Start budget* when the project has none.
  - *Edit line items* (drafts and submissions only) opens the grid editor.
  - *New FY<next> version* copies the selected version's line items into a
    draft for the next budget cycle (offered for active projects that don't
    have one yet).
  - *Edit details* changes status, approval and notes. Approve a budget here.
- **Line-item editor**: one row per line item, one column per fiscal year,
  with live totals. **+** buttons add a year at either end; *Add line item*
  adds a row; blank or zero amounts are removed; *Remove* deletes a line item.
- **Sidebar → Budgets**: all budget versions with filters for project,
  status, budget cycle and program.
- **Sidebar → Program Budget**: the roll-up (below).
- **Dashboard**: progress on the budget cycle being prepared (counts by
  status and how many active projects have no version yet) and this fiscal
  year's adopted program by project type.

## Program budget roll-up

For budget cycle N, each project contributes its **latest version prepared
for cycle N or earlier**, so a project that wasn't updated this year carries
its last budget forward:

- **Adopted**: only approved versions (approved now, or approved then and since
  superseded). This is the program as adopted for FY N, and also lets you look
  back at earlier cycles.
- **Proposed**: any version except rejected ones, so drafts and submissions
  for cycle N are included where they exist.

Columns: prior years (before FY N), FY N to FY N+4 (the five-year plan), the
five-year total, later years (shown only when anything falls after FY N+4) and
the total. The report is summarised by program and by category, then listed
project by project for each program. Cancelled projects, and projects with
nothing budgeted from FY N on, are left out.

Programs follow the project's current **project type**.

## API

`/api/budgets/`, `/api/budget-line-items/` and `/api/program-budget/`; see
[api.md](api.md).

## How it plugs into `pm`

`budgets/apps.py` imports `budgets/resources.py` and `budgets/demo.py` at
startup:

| Hook | Used for |
|---|---|
| `pm.resources.register(Resource(...))` | Budget list and generic create/edit/delete pages (`nav_group="Budgets"`). |
| `pm.resources.register_nav_link(NavLink(...))` | The *Program Budget* sidebar link. |
| `pm.resources.register_tab("project", Tab(...))` | The project *Budget* tab. |
| `pm.resources.register_dashboard_panel(fn)` | The budget-cycle panel. |
| `pm.demo.EXTENSIONS.append(fn)` | Demo budget history created by `seed_demo`. |

## Demo data

Every capital project gets an initial budget when it starts, then a new
version in most budget cycles while it's active: drafted between October and
January, submitted in spring and approved by the Board of Commissioners in
September. Earlier versions are a little cheaper and sometimes a year earlier
than later ones, as estimates grow and schedules slip. Around half the
development projects have a small capitalized-staff-time budget; the rest are
developer-funded. Versions for the cycle being prepared on the seed's
`--today` date are left as drafts or submissions.

## Ideas not built yet

- A side-by-side comparison of two versions, line by line.
- Comparing budget with actual spending (purchase orders and invoices by fiscal year).
- Funding sources (rates, bonds, grants, SRF loans) per line item.
- Stored, Board-adopted program budget records with their own approval.
