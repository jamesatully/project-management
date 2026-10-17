"""
Program budgets: project budgets rolled up by program (project type), fiscal
year and category for one budget cycle.

For cycle N, each project contributes its latest budget prepared for cycle N or
earlier, so projects that weren't updated this year carry their last budget
forward:

- ``adopted`` — only approved budgets (approved now, or approved then since
  superseded): the program as adopted for FY N.
- ``proposed`` — any budget except rejected ones: drafts and submissions for
  cycle N where they exist, else the project's adopted budget.

Columns are prior years (before FY N), FY N through FY N+4 (the five-year
plan), later years and the total. Cancelled projects, and projects with nothing
budgeted from FY N on, are left out.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from pm.models import Project

from .models import Budget, BudgetAmount, BudgetLineItem

BASES = {
    "adopted": ("Adopted", [Budget.Status.APPROVED, Budget.Status.SUPERSEDED]),
    "proposed": (
        "Proposed",
        [Budget.Status.DRAFT, Budget.Status.SUBMITTED, Budget.Status.APPROVED, Budget.Status.SUPERSEDED],
    ),
}
HORIZON = 5  # fiscal years shown individually


def selected_budgets(cycle, basis="adopted", program=None):
    """Each project's budget for ``cycle`` on ``basis`` (see module docstring)."""
    budgets = (
        Budget.objects.filter(budget_year__lte=cycle, status__in=BASES[basis][1])
        .exclude(project__status=Project.Status.CANCELLED)
        .order_by("project_id", "-budget_year")
        .distinct("project_id")
    )
    if program:
        budgets = budgets.filter(project__project_type=program)
    return budgets


class Row:
    """Prior / per-year / later / total figures for one row of the report."""

    def __init__(self, years):
        self.years = years
        self.prior = Decimal(0)
        self.by_year = dict.fromkeys(years, Decimal(0))
        self.later = Decimal(0)

    def add(self, fy, amount):
        if fy < self.years[0]:
            self.prior += amount
        elif fy > self.years[-1]:
            self.later += amount
        else:
            self.by_year[fy] += amount

    def merge(self, other):
        self.prior += other.prior
        self.later += other.later
        for fy, amount in other.by_year.items():
            self.by_year[fy] += amount

    @property
    def year_values(self):
        return [self.by_year[fy] for fy in self.years]

    @property
    def first_year(self):
        """The budget cycle's own fiscal year."""
        return self.by_year[self.years[0]]

    @property
    def plan_total(self):
        return sum(self.by_year.values(), Decimal(0))

    @property
    def total(self):
        return self.prior + self.plan_total + self.later

    @property
    def remaining(self):
        return self.plan_total + self.later

    def as_dict(self):
        return {
            "prior_years": self.prior,
            "fiscal_years": {f"FY{fy}": amount for fy, amount in self.by_year.items()},
            "five_year_total": self.plan_total,
            "later_years": self.later,
            "total": self.total,
        }


def program_budget(cycle, basis="adopted", program=None):
    """
    The roll-up for ``cycle``: ``{"years", "programs": [...], "categories": [...], "totals"}``.
    Each program has ``projects`` (rows with their budget), ``categories`` and ``totals``.
    """
    years = list(range(cycle, cycle + HORIZON))
    budgets = {b.pk: b for b in selected_budgets(cycle, basis, program).select_related("project")}
    sums = (
        BudgetAmount.objects.filter(line_item__budget__in=budgets)
        .values_list("line_item__budget", "line_item__category", "fiscal_year")
        .annotate(total=Sum("amount"))
    )
    per_budget = defaultdict(lambda: Row(years))
    per_budget_category = defaultdict(lambda: Row(years))
    for budget_id, category, fy, amount in sums:
        per_budget[budget_id].add(fy, amount)
        per_budget_category[budget_id, category].add(fy, amount)

    categories = BudgetLineItem.Category
    programs = []
    grand, grand_categories = Row(years), {c: Row(years) for c in categories.values}
    for type_value, type_label in Project.ProjectType.choices:
        rows = sorted(
            (
                {"project": b.project, "budget": b, "row": per_budget[pk]}
                for pk, b in budgets.items()
                if b.project.project_type == type_value and per_budget[pk].remaining
            ),
            key=lambda r: r["project"].project_id,
        )
        if not rows:
            continue
        totals, by_category = Row(years), {c: Row(years) for c in categories.values}
        for r in rows:
            totals.merge(r["row"])
            for c in categories.values:
                by_category[c].merge(per_budget_category[r["budget"].pk, c])
        grand.merge(totals)
        for c in categories.values:
            grand_categories[c].merge(by_category[c])
        programs.append(
            {
                "key": type_value,
                "label": type_label,
                "projects": rows,
                "categories": [{"key": c, "label": label, "row": by_category[c]} for c, label in categories.choices],
                "totals": totals,
            }
        )
    return {
        "cycle": cycle,
        "basis": basis,
        "basis_label": BASES[basis][0],
        "years": years,
        "programs": programs,
        "categories": [{"key": c, "label": label, "row": grand_categories[c]} for c, label in categories.choices],
        "totals": grand,
    }
