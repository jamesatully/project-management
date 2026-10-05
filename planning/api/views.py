"""Planning REST API. Same conventions as pm.api: filters, ?search=, ?ordering=, pagination."""
from rest_framework import viewsets

from .. import filters
from ..models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder
from . import serializers


class ProjectPlanViewSet(viewsets.ModelViewSet):
    queryset = ProjectPlan.objects.select_related("project")
    serializer_class = serializers.ProjectPlanSerializer
    filterset_class = filters.ProjectPlanFilter
    search_fields = ["project__name", "project__project_id", "problem_statement", "scope_in", "scope_out"]
    ordering_fields = ["status", "approved_date", "updated_at"]


class ObjectiveViewSet(viewsets.ModelViewSet):
    queryset = Objective.objects.all()
    serializer_class = serializers.ObjectiveSerializer
    filterset_class = filters.ObjectiveFilter
    search_fields = ["description", "success_measure"]
    ordering_fields = ["order", "target_date", "status"]


class RiskViewSet(viewsets.ModelViewSet):
    queryset = Risk.objects.select_related("project")
    serializer_class = serializers.RiskSerializer
    filterset_class = filters.RiskFilter
    search_fields = ["title", "description", "mitigation", "owner", "project__name"]
    ordering_fields = ["score", "likelihood", "impact", "review_date", "identified_date", "status"]


class StakeholderViewSet(viewsets.ModelViewSet):
    queryset = Stakeholder.objects.all()
    serializer_class = serializers.StakeholderSerializer
    filterset_class = filters.StakeholderFilter
    search_fields = ["name", "organization", "role"]
    ordering_fields = ["name", "organization", "influence", "interest"]


class MilestoneViewSet(viewsets.ModelViewSet):
    queryset = Milestone.objects.all()
    serializer_class = serializers.MilestoneSerializer
    filterset_class = filters.MilestoneFilter
    search_fields = ["name"]
    ordering_fields = ["planned_date", "forecast_date", "actual_date", "status"]


class CommunicationItemViewSet(viewsets.ModelViewSet):
    queryset = CommunicationItem.objects.all()
    serializer_class = serializers.CommunicationItemSerializer
    filterset_class = filters.CommunicationItemFilter
    search_fields = ["purpose", "audience", "owner"]
    ordering_fields = ["purpose", "method", "frequency"]


class ActivityNoteViewSet(viewsets.ModelViewSet):
    queryset = ActivityNote.objects.select_related("project")
    serializer_class = serializers.ActivityNoteSerializer
    filterset_class = filters.ActivityNoteFilter
    search_fields = ["title", "body", "author_name", "project__name"]
    ordering_fields = ["note_date", "period", "note_type"]
