"""FilterSets shared by the budgets API and list page."""

import django_filters

from pm.models import Project

from .models import Budget, BudgetLineItem


class BudgetFilter(django_filters.FilterSet):
    budget_year = django_filters.NumberFilter(label="Budget cycle (FY)")
    project_type = django_filters.ChoiceFilter(
        field_name="project__project_type", choices=Project.ProjectType.choices, label="Program"
    )

    class Meta:
        model = Budget
        fields = ["project", "status", "budget_year", "project_type"]


class BudgetLineItemFilter(django_filters.FilterSet):
    budget = django_filters.UUIDFilter()
    project = django_filters.UUIDFilter(field_name="budget__project")

    class Meta:
        model = BudgetLineItem
        fields = ["budget", "project", "category"]
