"""Budgets REST API. Same conventions as pm.api: filters, ?search=, ?ordering=, pagination."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from pm.models import Project

from .. import filters, rollup
from ..models import Budget, BudgetLineItem, check_editable, current_fiscal_year
from . import serializers


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.select_related("project").prefetch_related("line_items__amounts")
    serializer_class = serializers.BudgetSerializer
    filterset_class = filters.BudgetFilter
    search_fields = ["project__name", "project__project_id", "prepared_by", "notes"]
    ordering_fields = ["budget_year", "status", "approved_date", "updated_at"]


class BudgetLineItemViewSet(viewsets.ModelViewSet):
    queryset = BudgetLineItem.objects.select_related("budget").prefetch_related("amounts")
    serializer_class = serializers.BudgetLineItemSerializer
    filterset_class = filters.BudgetLineItemFilter
    search_fields = ["description"]
    ordering_fields = ["category", "created_at"]

    def perform_destroy(self, instance):
        try:
            check_editable(instance.budget)
        except DjangoValidationError as exc:
            raise drf_serializers.ValidationError(exc.messages)
        instance.delete()


def money(value):
    return f"{value:.2f}"


def categories(items):
    return [{"category": c["key"], "category_display": c["label"], **row_dict(c["row"])} for c in items]


def row_dict(row):
    data = row.as_dict()
    return {
        "prior_years": money(data["prior_years"]),
        "fiscal_years": {fy: money(v) for fy, v in data["fiscal_years"].items()},
        "five_year_total": money(data["five_year_total"]),
        "later_years": money(data["later_years"]),
        "total": money(data["total"]),
    }


class ProgramBudgetView(APIView):
    """Project budgets rolled up by program, fiscal year and category for one budget cycle."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "cycle", int, description="Budget cycle (fiscal year); defaults to the current fiscal year."
            ),
            OpenApiParameter("basis", str, enum=list(rollup.BASES), description="adopted (default) or proposed."),
            OpenApiParameter("program", str, enum=Project.ProjectType.values, description="Limit to one program."),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request):
        try:
            cycle = int(request.query_params.get("cycle", current_fiscal_year()))
        except ValueError:
            raise drf_serializers.ValidationError({"cycle": "Enter a fiscal year, e.g. 2027."})
        basis = request.query_params.get("basis", "adopted")
        if basis not in rollup.BASES:
            raise drf_serializers.ValidationError({"basis": f"Choose one of: {', '.join(rollup.BASES)}."})
        program = request.query_params.get("program") or None
        if program and program not in Project.ProjectType.values:
            raise drf_serializers.ValidationError(
                {"program": f"Choose one of: {', '.join(Project.ProjectType.values)}."}
            )

        report = rollup.program_budget(cycle, basis, program)
        return Response(
            {
                "cycle": cycle,
                "basis": basis,
                "fiscal_years": [f"FY{fy}" for fy in report["years"]],
                "programs": [
                    {
                        "program": p["key"],
                        "program_display": p["label"],
                        "totals": row_dict(p["totals"]),
                        "categories": categories(p["categories"]),
                        "projects": [
                            {
                                "project": r["project"].pk,
                                "project_id": r["project"].project_id,
                                "name": r["project"].name,
                                "budget": r["budget"].pk,
                                "budget_year": r["budget"].budget_year,
                                "budget_status": r["budget"].status,
                                **row_dict(r["row"]),
                            }
                            for r in p["projects"]
                        ],
                    }
                    for p in report["programs"]
                ],
                "categories": categories(report["categories"]),
                "totals": row_dict(report["totals"]),
            }
        )
