"""Builders for budget tests."""

import datetime
from decimal import Decimal

from ..models import Budget, BudgetAmount, BudgetLineItem


def make_budget(project, budget_year=2027, status=Budget.Status.DRAFT, **kw):
    if status == Budget.Status.APPROVED:
        kw = {"approved_by": "Board of Commissioners", "approved_date": datetime.date(budget_year - 1, 9, 15), **kw}
    return Budget.objects.create(project=project, budget_year=budget_year, status=status, **kw)


def add_line(budget, category=BudgetLineItem.Category.CONSTRUCTION, amounts=None, description=""):
    """A line item with ``amounts`` {fiscal_year: amount}, written directly (bypassing the editable check)."""
    item = BudgetLineItem.objects.create(budget=budget, category=category, description=description)
    for fy, amount in (amounts or {}).items():
        BudgetAmount.objects.create(line_item=item, fiscal_year=fy, amount=Decimal(amount))
    return item
