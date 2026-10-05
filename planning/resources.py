"""
Registers planning with the pm app's UI: generic list/detail/form pages for
each model, sidebar entries, the project "Plan" and "Activity" tabs,
dashboard panels and status badge colours. Imported from PlanningConfig.ready().
"""
from pm import display
from pm.resources import Column, Resource, Tab, register, register_dashboard_panel, register_tab

from . import filters, forms, views
from .models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder

display.STATUS_COLORS.update(
    {
        "IN_REVIEW": "amber",
        "NOT_STARTED": "slate",
        "ON_TRACK": "sky",
        "IN_PROGRESS": "sky",
        "AT_RISK": "orange",
        "ACHIEVED": "emerald",
        "NOT_ACHIEVED": "rose",
        "MITIGATING": "amber",
        "MISSED": "rose",
    }
)

for resource in [
    Resource(
        key="plan", url_prefix="plans", nav_group="Planning", icon="map",
        model=ProjectPlan, form_class=forms.ProjectPlanForm, filterset_class=filters.ProjectPlanFilter,
        columns=[
            Column("project", "Project", "link"),
            Column("status", "Status", "status"),
            Column("approved_by", "Approved By"),
            Column("approved_date", "Approved", "date"),
            Column("updated_at", "Last Updated", "date"),
        ],
        search_fields=["project__name", "project__project_id", "problem_statement", "scope_in", "scope_out"],
        select_related=["project"],
    ),
    Resource(
        key="risk", url_prefix="risks", nav_group="Planning", icon="shield",
        model=Risk, form_class=forms.RiskForm, filterset_class=filters.RiskFilter,
        columns=[
            Column("title", "Risk", "link"),
            Column("project", "Project", "fk"),
            Column("category", "Category"),
            Column("score", "Score", "score"),
            Column("status", "Status", "status"),
            Column("owner", "Owner"),
            Column("review_date", "Next Review", "date"),
        ],
        search_fields=["title", "description", "mitigation", "owner", "project__name", "project__project_id"],
        select_related=["project"],
    ),
    Resource(
        key="milestone", url_prefix="milestones", nav_group="Planning", icon="flag",
        model=Milestone, form_class=forms.MilestoneForm, filterset_class=filters.MilestoneFilter,
        columns=[
            Column("name", "Milestone", "link"),
            Column("project", "Project", "fk"),
            Column("planned_date", "Planned", "date"),
            Column("forecast_date", "Forecast", "date"),
            Column("actual_date", "Actual", "date"),
            Column("variance_days", "Variance", "days"),
            Column("status", "Status", "status"),
        ],
        search_fields=["name", "project__name", "project__project_id"],
        select_related=["project"],
    ),
    Resource(
        key="activitynote", url_prefix="activity", nav_group="Planning", icon="chat",
        model=ActivityNote, form_class=forms.ActivityNoteForm, filterset_class=filters.ActivityNoteFilter,
        columns=[
            Column("note_date", "Date", "link"),
            Column("project", "Project", "fk"),
            Column("note_type", "Type"),
            Column("period", "Month", "month"),
            Column("author_name", "Author"),
            Column("title", "Title"),
        ],
        search_fields=["title", "body", "author_name", "project__name", "project__project_id"],
        select_related=["project"],
    ),
    # Plan sections edited from the Plan tab; reachable but not in the sidebar.
    Resource(
        key="objective", url_prefix="objectives", nav_group=None, icon="flag",
        model=Objective, form_class=forms.ObjectiveForm, filterset_class=filters.ObjectiveFilter,
        columns=[
            Column("description", "Objective", "link"),
            Column("project", "Project", "fk"),
            Column("success_measure", "Success Measure"),
            Column("target_date", "Target", "date"),
            Column("status", "Status", "status"),
        ],
        search_fields=["description", "success_measure", "project__name"],
        select_related=["project"],
    ),
    Resource(
        key="stakeholder", url_prefix="stakeholders", nav_group=None, icon="users",
        model=Stakeholder, form_class=forms.StakeholderForm, filterset_class=filters.StakeholderFilter,
        columns=[
            Column("name", "Name", "link"),
            Column("project", "Project", "fk"),
            Column("organization", "Organization"),
            Column("role", "Role"),
            Column("influence", "Influence"),
            Column("interest", "Interest"),
            Column("engagement_strategy", "Strategy"),
        ],
        search_fields=["name", "organization", "role", "project__name"],
        select_related=["project"],
    ),
    Resource(
        key="communicationitem", url_prefix="communication-plan", nav_group=None, icon="chat",
        model=CommunicationItem, form_class=forms.CommunicationItemForm, filterset_class=filters.CommunicationItemFilter,
        columns=[
            Column("purpose", "What", "link"),
            Column("project", "Project", "fk"),
            Column("audience", "Audience"),
            Column("method", "Method"),
            Column("frequency", "Frequency"),
            Column("owner", "Owner"),
        ],
        search_fields=["purpose", "audience", "owner", "project__name"],
        select_related=["project"],
    ),
]:
    register(resource)

register_tab("project", Tab("Plan", "planning:project-plan"))
register_tab("project", Tab("Activity", "planning:project-activity"))
register_dashboard_panel(views.updates_due_panel)
register_dashboard_panel(views.top_risks_panel)
