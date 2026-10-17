"""
Budget pages: the project "Budget" tab (versions and the selected budget's
fiscal-year grid), the line-item grid editor, "new version" (copy a budget into
the next budget cycle), the Program Budget roll-up and a dashboard panel.

A budget's details (cycle, status, approval) are edited through pm's generic
form views; links here pass ``?next=<this page>`` to come back afterwards.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max, Min
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.views import generic

from pm.models import Project
from pm.resources import REGISTRY
from pm.views import detail_tabs

from . import rollup
from .forms import line_item_formset
from .models import Budget, BudgetAmount, current_fiscal_year, next_budget_year

ACTIVE_STATUSES = [Project.Status.PLANNING, Project.Status.DESIGN, Project.Status.CONSTRUCTION, Project.Status.ON_HOLD]
DEFAULT_YEARS = 5  # columns offered for a budget with no amounts yet


def with_next(url, next_url):
    return f"{url}?{urlencode({'next': next_url})}"


def budget_grid(budget):
    """Line items (in category order) × fiscal years, with row, column and category totals."""
    items = sorted(budget.line_items.prefetch_related("amounts"), key=lambda i: i.sort_key)
    amounts = {(a.line_item_id, a.fiscal_year): a.amount for i in items for a in i.amounts.all()}
    years = sorted({fy for _, fy in amounts})
    rows, categories = [], {}
    for item in items:
        cells = [amounts.get((item.pk, fy)) for fy in years]
        total = sum((c for c in cells if c), Decimal(0))
        rows.append({"item": item, "cells": cells, "total": total})
        cat = categories.setdefault(item.category, {"label": item.get_category_display(), "total": Decimal(0)})
        cat["total"] += total
    column_totals = [sum((r["cells"][i] or 0 for r in rows), Decimal(0)) for i in range(len(years))]
    return {
        "years": years,
        "rows": rows,
        "column_totals": column_totals,
        "total": sum(column_totals, Decimal(0)),
        "categories": list(categories.values()),
    }


def default_years(budget):
    """Fiscal-year columns for the editor: every year with an amount, else five from the budget cycle."""
    years = BudgetAmount.objects.filter(line_item__budget=budget).aggregate(
        lo=Min("fiscal_year"), hi=Max("fiscal_year")
    )
    if years["lo"] is None:
        return budget.budget_year, budget.budget_year + DEFAULT_YEARS - 1
    return years["lo"], years["hi"]


class ProjectBudgetView(LoginRequiredMixin, generic.DetailView):
    """The project's Budget tab."""

    model = Project
    context_object_name = "project"
    template_name = "budgets/project_budget.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project, here = self.object, self.request.path
        budgets = list(project.budgets.order_by("budget_year"))

        # Versions, oldest first for the change column, then shown newest first.
        versions, previous = [], None
        for b in budgets:
            change = b.total - previous.total if previous else None
            versions.append({"budget": b, "change": change})
            if b.status != Budget.Status.REJECTED:
                previous = b
        versions.reverse()

        selected = None
        version_id = self.request.GET.get("version")
        if version_id:
            selected = next((b for b in budgets if str(b.pk) == version_id), None)
        if selected is None:
            approved = [b for b in budgets if b.status == Budget.Status.APPROVED]
            selected = approved[-1] if approved else (budgets[-1] if budgets else None)

        next_year = next_budget_year()
        ctx.update(
            resource=REGISTRY["project"],
            active_nav="project",
            tabs=detail_tabs("project", project, "budgets:project-budget"),
            back_url=reverse("pm:project-list"),
            versions=versions,
            selected=selected,
            next_year=next_year,
            create_url=f"{reverse('pm:budget-create')}?"
            + urlencode({"project": project.pk, "prepared_by": project.project_manager, "next": here}),
        )
        if selected:
            back = selected.get_absolute_url()
            ctx.update(
                grid=budget_grid(selected),
                edit_url=with_next(reverse("pm:budget-update", args=[selected.pk]), back),
                delete_url=with_next(reverse("pm:budget-delete", args=[selected.pk]), here),
                lines_url=reverse("budgets:line-items", args=[selected.pk]),
                copy_url=reverse("budgets:copy", args=[selected.pk]),
                can_copy=project.status in ACTIVE_STATUSES and not any(b.budget_year == next_year for b in budgets),
            )
        return ctx


class BudgetLineItemsView(LoginRequiredMixin, generic.DetailView):
    """Spreadsheet-style editor: one row per line item, one column per fiscal year."""

    model = Budget
    context_object_name = "budget"
    template_name = "budgets/line_items.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            budget = get_object_or_404(Budget, pk=kwargs["pk"])
            if not budget.is_editable:
                messages.error(
                    request,
                    f"The {budget.name.lower()} is {budget.get_status_display().lower()}, "
                    "so its line items can't change. Start a new version to update it.",
                )
                return redirect(budget.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def year_range(self, data):
        lo, hi = default_years(self.object)
        try:
            lo = min(lo, int(data.get("fy_from", lo)))
            hi = max(hi, int(data.get("fy_to", hi)))
        except ValueError:
            pass
        if data.get("add_year") == "before":
            lo -= 1
        elif data.get("add_year") == "after":
            hi += 1
        return lo, hi

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        lo, hi = self.year_range(request.GET)
        return self.render(line_item_formset(self.object, range(lo, hi + 1)), lo, hi)

    def post(self, request, *args, **kwargs):
        self.object = budget = self.get_object()
        lo, hi = self.year_range(request.POST)
        years = range(lo, hi + 1)
        data = request.POST.copy()
        if "add_row" in data:
            data["lines-TOTAL_FORMS"] = int(data.get("lines-TOTAL_FORMS", 0)) + 1
        formset = line_item_formset(budget, years, data)
        if "add_row" in data or "add_year" in data:
            return self.render(formset, lo, hi)  # redraw with the extra row/column; nothing saved yet
        if not formset.is_valid():
            return self.render(formset, lo, hi)
        formset.save_all()
        messages.success(request, f"{budget.name} line items saved.")
        return redirect(budget.get_absolute_url())

    def render(self, formset, lo, hi):
        ctx = self.get_context_data(
            formset=formset,
            years=list(range(lo, hi + 1)),
            fy_from=lo,
            fy_to=hi,
            project=self.object.project,
            cancel_url=self.object.get_absolute_url(),
            active_nav="budget",
        )
        return self.render_to_response(ctx)


class BudgetCopyView(LoginRequiredMixin, generic.View):
    """POST: start next cycle's draft from this budget's line items and amounts."""

    def post(self, request, pk):
        source = get_object_or_404(Budget.objects.select_related("project"), pk=pk)
        year = next_budget_year()
        if source.project.budgets.filter(budget_year=year).exists():
            messages.error(request, f"This project already has an FY{year} budget.")
            return redirect(source.get_absolute_url())
        new = source.copy(year, prepared_by=source.project.project_manager)
        messages.success(
            request, f"FY{year} draft budget started from the {source.name.lower()}. Update the figures below."
        )
        return redirect("budgets:line-items", pk=new.pk)


class ProgramBudgetView(LoginRequiredMixin, generic.TemplateView):
    """Project budgets rolled up into the CIP Expansion, CIP R&R and Development programs."""

    template_name = "budgets/program.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET
        cycles = sorted(
            set(Budget.objects.values_list("budget_year", flat=True).distinct())
            | {current_fiscal_year(), next_budget_year()},
            reverse=True,
        )
        try:
            cycle = int(params.get("cycle", current_fiscal_year()))
        except ValueError:
            cycle = current_fiscal_year()
        basis = params.get("basis") if params.get("basis") in rollup.BASES else "adopted"
        program = params.get("program") if params.get("program") in Project.ProjectType.values else ""
        report = rollup.program_budget(cycle, basis, program or None)
        ctx.update(
            active_nav="programbudget",
            report=report,
            show_later=bool(report["totals"].later),  # the five-year window usually covers everything
            cycles=cycles,
            cycle=cycle,
            basis=basis,
            bases=[(key, label) for key, (label, _) in rollup.BASES.items()],
            program=program,
            programs=Project.ProjectType.choices,
            api_url=f"{reverse('api-program-budget')}?{urlencode({'cycle': cycle, 'basis': basis})}",
        )
        return ctx


# --- Dashboard panel (registered in budgets/resources.py) ----------------------


def budget_cycle_panel(request):
    """Progress of the budget cycle being prepared, and the adopted program for this fiscal year."""
    cycle, fy = next_budget_year(), current_fiscal_year()
    counts = dict(Budget.objects.filter(budget_year=cycle).values_list("status").annotate(n=Count("id")))
    active = Project.objects.filter(status__in=ACTIVE_STATUSES)
    report = rollup.program_budget(fy, "adopted")
    return {
        "template": "budgets/panel_budget_cycle.html",
        "cycle": cycle,
        "fy": fy,
        "statuses": [
            {"label": label, "count": counts.get(value, 0), "value": value}
            for value, label in Budget.Status.choices
            if value != Budget.Status.SUPERSEDED
        ],
        "missing": active.exclude(budgets__budget_year=cycle).count(),
        "active_count": active.count(),
        "programs": [{"label": p["label"], "amount": p["totals"].by_year[fy]} for p in report["programs"]],
        "fy_total": report["totals"].by_year[fy],
        "cycle_url": f"{reverse('pm:budget-list')}?{urlencode({'budget_year': cycle})}",
        "program_url": reverse("budgets:program"),
    }
