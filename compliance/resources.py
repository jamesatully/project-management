"""
Registers compliance with the pm app's UI: generic list/detail/form pages for
permits and compliance milestones, sidebar entries, related tables on compliance
unit, contact and document pages, the dashboard panel and status badge colours.
Imported from ComplianceConfig.ready().
"""
from pm import display
from pm.resources import Column, Related, Resource, register, register_dashboard_panel, register_related

from . import filters, forms, views
from .models import ComplianceMilestone, Permit

display.STATUS_COLORS.update(
    {
        # Permits
        "PENDING": "sky",
        "ACTIVE": "emerald",
        "EXTENDED": "amber",
        "EXPIRED": "rose",
        "TERMINATED": "slate",
        # Milestones (NOT_STARTED, IN_PROGRESS, SUBMITTED and COMPLETE are already set by other apps)
        ComplianceMilestone.OVERDUE: "rose",
        "NOT_STARTED": "slate",
        "IN_PROGRESS": "sky",
        "SUBMITTED": "amber",
        "COMPLETE": "emerald",
    }
)

for resource in [
    Resource(
        key="permit", url_prefix="permits", nav_group="Compliance", icon="badge",
        model=Permit, form_class=forms.PermitForm, filterset_class=filters.PermitFilter,
        columns=[
            Column("name", "Permit", "link"),
            Column("permit_number", "Permit #"),
            Column("compliance_unit", "Compliance Unit", "fk"),
            Column("status", "Status", "status"),
            Column("expiration_date", "Expires", "date"),
            Column("next_due", "Next Due", "date"),
        ],
        search_fields=["name", "permit_number", "issuing_agency", "description", "compliance_unit__name"],
        select_related=["compliance_unit"],
        related=[Related("milestones", "compliancemilestone", "permit")],
    ),
    Resource(
        key="compliancemilestone", url_prefix="compliance-milestones", nav_group="Compliance", icon="flag",
        model=ComplianceMilestone, form_class=forms.ComplianceMilestoneForm,
        filterset_class=filters.ComplianceMilestoneFilter,
        columns=[
            Column("name", "Milestone", "link"),
            Column("permit", "Permit", "fk"),
            Column("permit_condition", "Condition"),
            Column("due_date", "Due", "date"),
            Column("target_date", "Target", "date"),
            Column("current_status", "Status", "status"),
            Column("manager", "Manager", "person"),
        ],
        search_fields=["name", "permit_condition", "description", "permit__name", "permit__permit_number",
                       "manager__name"],
        select_related=["permit", "manager"],
        detail_fields=[
            "permit", "name", "permit_condition", "manager", Column("current_status", "Status", "status"),
            "due_date", "target_date", "submitted_date", Column("variance_days", "Submitted vs. due", "days"),
            "submittal_document", "description",
        ],
    ),
]:
    register(resource)

register_related("complianceunit", Related("permits", "permit", "compliance_unit"))
register_related("contact", Related("compliance_milestones", "compliancemilestone", "manager"))
# Condition and target date are left off on document pages so the table fits.
register_related(
    "document",
    Related(
        "compliance_milestones", "compliancemilestone", "submittal_document", exclude=("permit_condition", "target_date")
    ),
)
register_dashboard_panel(views.compliance_deadlines_panel)
