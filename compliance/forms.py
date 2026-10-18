from django import forms

from pm.forms import StyledModelForm
from pm.models import Document

from .models import ComplianceMilestone, Permit


def staff_label(contact):
    """Manager choices are internal contacts who share the utility as organization, so show job titles."""
    return f"{contact.name} — {contact.title}" if contact.title else contact.name


class PermitForm(StyledModelForm):
    class Meta:
        model = Permit
        fields = [
            "compliance_unit", "name", "permit_number", "issuing_agency", "manager", "status",
            "effective_date", "expiration_date", "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].label_from_instance = staff_label


class ComplianceMilestoneForm(StyledModelForm):
    class Meta:
        model = ComplianceMilestone
        fields = [
            "permit", "name", "permit_condition", "manager", "status", "due_date", "target_date",
            "submitted_date", "submittal_document", "description",
        ]
        help_texts = {
            "submittal_document": "Documents filed under the permit's compliance unit. Not listed? Add it under Documents first."
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].label_from_instance = staff_label

        # Only documents filed under a compliance unit can be submittals; narrow to the permit's unit when known.
        documents = Document.objects.filter(compliance_unit__isnull=False).select_related("compliance_unit")
        permit = self.selected_permit()
        if permit:
            documents = documents.filter(compliance_unit=permit.compliance_unit_id)
        field = self.fields["submittal_document"]
        field.queryset = documents
        field.label_from_instance = lambda d: f"{d.subject} ({d.document_date:%b %-d, %Y})"

    def selected_permit(self):
        """The permit chosen in the submitted data, the ?permit= pre-fill, or the saved instance."""
        value = self.data.get(self.add_prefix("permit")) if self.is_bound else self.initial.get("permit")
        if not value and self.instance.permit_id:
            return self.instance.permit
        try:
            return Permit.objects.filter(pk=value).first() if value else None
        except (ValueError, forms.ValidationError):
            return None
