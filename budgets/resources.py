"""
Registers budgets with the pm app's UI: generic list/form pages for budgets, the
sidebar entries, the project "Budget" tab, the dashboard panel and status badge
colours. Imported from BudgetsConfig.ready().
"""
from pm import display
from pm.resources import (
    Column, NavLink, Resource, Tab, register, register_dashboard_panel, register_nav_link, register_tab,
)

from . import filters, forms, views
from .models import Budget

display.STATUS_COLORS.update({"SUBMITTED": "amber", "SUPERSEDED": "slate"})

register(
    Resource(
        key="budget", url_prefix="budgets", nav_group="Budgets", icon="banknotes",
        model=Budget, form_class=forms.BudgetForm, filterset_class=filters.BudgetFilter,
        columns=[
            Column("name", "Budget", "link"),
            Column("project", "Project", "fk"),
            Column("status", "Status", "status"),
            Column("total", "Total", "money"),
            Column("approved_date", "Approved", "date"),
        ],
        search_fields=["project__name", "project__project_id", "prepared_by", "notes"],
        select_related=["project"],
    )
)
register_nav_link(NavLink("Budgets", "Program Budget", "budgets:program", "chart", "programbudget"))
register_tab("project", Tab("Budget", "budgets:project-budget"))
register_dashboard_panel(views.budget_cycle_panel)
