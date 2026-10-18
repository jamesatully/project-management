from rest_framework import serializers

from pm.api.serializers import ModelCleanMixin

from ..models import ComplianceMilestone, Permit

AUDIT = ["created_at", "updated_at"]


class PermitSerializer(ModelCleanMixin, serializers.ModelSerializer):
    compliance_unit_name = serializers.CharField(source="compliance_unit.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Permit
        fields = [
            "id", "compliance_unit", "compliance_unit_name", "name", "permit_number", "issuing_agency",
            "status", "status_display", "effective_date", "expiration_date", "description", *AUDIT,
        ]


class ComplianceMilestoneSerializer(ModelCleanMixin, serializers.ModelSerializer):
    """``status`` is the stored progress state; ``current_status`` is ``OVERDUE`` when past due and still open."""

    permit_name = serializers.CharField(source="permit.name", read_only=True)
    manager_name = serializers.CharField(source="manager.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    current_status = serializers.CharField(read_only=True)
    current_status_display = serializers.CharField(source="get_current_status_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    variance_days = serializers.IntegerField(read_only=True)
    submittal_document_subject = serializers.CharField(
        source="submittal_document.subject", read_only=True, default=None
    )

    class Meta:
        model = ComplianceMilestone
        fields = [
            "id", "permit", "permit_name", "manager", "manager_name", "name", "permit_condition",
            "due_date", "target_date", "status", "status_display", "current_status", "current_status_display",
            "is_overdue", "submitted_date", "variance_days", "submittal_document", "submittal_document_subject",
            "description", *AUDIT,
        ]
