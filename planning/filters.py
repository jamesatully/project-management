"""FilterSets shared by the planning API and list pages."""
import django_filters

from .models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder


class ProjectPlanFilter(django_filters.FilterSet):
    class Meta:
        model = ProjectPlan
        fields = ["status", "project"]


class ObjectiveFilter(django_filters.FilterSet):
    class Meta:
        model = Objective
        fields = ["project", "status"]


class RiskFilter(django_filters.FilterSet):
    score_min = django_filters.NumberFilter(field_name="score", lookup_expr="gte", label="Min score")

    class Meta:
        model = Risk
        fields = ["project", "status", "category"]


class StakeholderFilter(django_filters.FilterSet):
    class Meta:
        model = Stakeholder
        fields = ["project", "influence", "interest"]


class MilestoneFilter(django_filters.FilterSet):
    planned_date_after = django_filters.DateFilter(field_name="planned_date", lookup_expr="gte", label="From")
    planned_date_before = django_filters.DateFilter(field_name="planned_date", lookup_expr="lte", label="To")

    class Meta:
        model = Milestone
        fields = ["project", "status"]


class CommunicationItemFilter(django_filters.FilterSet):
    class Meta:
        model = CommunicationItem
        fields = ["project", "method", "frequency"]


class ActivityNoteFilter(django_filters.FilterSet):
    note_date_after = django_filters.DateFilter(field_name="note_date", lookup_expr="gte", label="From")
    note_date_before = django_filters.DateFilter(field_name="note_date", lookup_expr="lte", label="To")

    class Meta:
        model = ActivityNote
        fields = ["project", "note_type"]
