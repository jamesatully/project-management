"""FilterSets shared by the compliance API and list pages."""
import django_filters
from django import forms
from django.utils import timezone

from pm.filters import ContactNameFilter
from pm.models import ComplianceUnit, Contact

from .models import ComplianceMilestone, Permit

S = ComplianceMilestone.Status


class PermitFilter(django_filters.FilterSet):
    compliance_unit = django_filters.ModelChoiceFilter(queryset=ComplianceUnit.objects.all(), label="Compliance unit")
    # Only contacts who manage at least one permit.
    manager = ContactNameFilter(
        queryset=Contact.objects.filter(managed_permits__isnull=False).distinct(), label="Permit manager"
    )
    expiration_date_before = django_filters.DateFilter(
        field_name="expiration_date", lookup_expr="lte", label="Expires before"
    )

    class Meta:
        model = Permit
        fields = ["compliance_unit", "manager", "status", "expiration_date_before"]


class ComplianceMilestoneFilter(django_filters.FilterSet):
    """``status`` matches the status shown in the app, so Not Started / In Progress exclude overdue milestones."""

    STATUS_CHOICES = [
        ("OPEN", "Open (not yet submitted)"),
        (ComplianceMilestone.OVERDUE, "Overdue"),
        *S.choices,
    ]

    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, method="filter_status", label="Status")
    permit = django_filters.ModelChoiceFilter(queryset=Permit.objects.all(), label="Permit")
    compliance_unit = django_filters.ModelChoiceFilter(
        field_name="permit__compliance_unit", queryset=ComplianceUnit.objects.all(), label="Compliance unit"
    )
    # Only contacts who manage at least one milestone.
    manager = ContactNameFilter(
        queryset=Contact.objects.filter(compliance_milestones__isnull=False).distinct(), label="Milestone manager"
    )
    due_date_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte", label="Due from")
    due_date_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte", label="Due to")
    # Used by "View all" on a document's page.
    submittal_document = django_filters.UUIDFilter(widget=forms.HiddenInput)

    class Meta:
        model = ComplianceMilestone
        fields = ["status", "permit", "compliance_unit", "manager", "due_date_after", "due_date_before",
                  "submittal_document"]

    def filter_status(self, queryset, name, value):
        today = timezone.localdate()
        if value == "OPEN":
            return queryset.open()
        if value == ComplianceMilestone.OVERDUE:
            return queryset.overdue(today)
        if value in ComplianceMilestone.MET_STATUSES:
            return queryset.filter(status=value)
        return queryset.filter(status=value, due_date__gte=today)
