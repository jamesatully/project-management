from rest_framework import serializers

from pm.api.serializers import ModelCleanMixin

from ..models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder, first_of_month

AUDIT = ["created_at", "updated_at"]


class ProjectPlanSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ProjectPlan
        fields = [
            "id", "project", "project_display", "status", "status_display", "problem_statement",
            "scope_in", "scope_out", "approved_by", "approved_date", *AUDIT,
        ]


class ObjectiveSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Objective
        fields = ["id", "project", "description", "success_measure", "target_date", "status", "status_display", "order", *AUDIT]


class RiskSerializer(serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Risk
        fields = [
            "id", "project", "project_display", "title", "description", "category", "category_display",
            "likelihood", "impact", "score", "owner", "mitigation", "status", "status_display",
            "identified_date", "review_date", *AUDIT,
        ]
        read_only_fields = ["score"]


class StakeholderSerializer(serializers.ModelSerializer):
    engagement_strategy = serializers.CharField(read_only=True)

    class Meta:
        model = Stakeholder
        fields = [
            "id", "project", "name", "organization", "role", "influence", "interest",
            "engagement_strategy", "contact", "engagement_notes", *AUDIT,
        ]


class MilestoneSerializer(ModelCleanMixin, serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    variance_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Milestone
        fields = [
            "id", "project", "name", "planned_date", "forecast_date", "actual_date", "variance_days",
            "status", "status_display", *AUDIT,
        ]


class CommunicationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationItem
        fields = ["id", "project", "purpose", "audience", "method", "frequency", "owner", "notes", *AUDIT]


class ActivityNoteSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)
    note_type_display = serializers.CharField(source="get_note_type_display", read_only=True)

    class Meta:
        model = ActivityNote
        fields = [
            "id", "project", "project_display", "note_type", "note_type_display", "period", "note_date",
            "author_name", "title", "body", *AUDIT,
        ]

    def validate_period(self, value):
        # Any date in the month is accepted and stored as the 1st.
        return first_of_month(value) if value else value
