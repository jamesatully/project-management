from django import forms

from pm.forms import StyledModelForm

from .models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder


class ProjectPlanForm(StyledModelForm):
    class Meta:
        model = ProjectPlan
        fields = ["project", "status", "approved_by", "approved_date", "problem_statement", "scope_in", "scope_out"]
        widgets = {f: forms.Textarea(attrs={"rows": 6}) for f in ["problem_statement", "scope_in", "scope_out"]}


class ObjectiveForm(StyledModelForm):
    class Meta:
        model = Objective
        fields = ["project", "description", "success_measure", "target_date", "status", "order"]


class RiskForm(StyledModelForm):
    class Meta:
        model = Risk
        fields = [
            "project", "title", "category", "status", "likelihood", "impact", "owner",
            "identified_date", "review_date", "description", "mitigation",
        ]


class StakeholderForm(StyledModelForm):
    class Meta:
        model = Stakeholder
        fields = ["project", "name", "organization", "role", "influence", "interest", "contact", "engagement_notes"]


class MilestoneForm(StyledModelForm):
    class Meta:
        model = Milestone
        fields = ["project", "name", "status", "planned_date", "forecast_date", "actual_date"]


class CommunicationItemForm(StyledModelForm):
    class Meta:
        model = CommunicationItem
        fields = ["project", "purpose", "audience", "method", "frequency", "owner", "notes"]


class ActivityNoteForm(StyledModelForm):
    period = forms.DateField(
        label="Reporting month",
        required=False,
        input_formats=["%Y-%m", "%Y-%m-%d"],
        help_text="Required for monthly updates.",
    )

    class Meta:
        model = ActivityNote
        fields = ["project", "note_type", "period", "note_date", "author_name", "title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A native month picker; StyledModelForm made every DateInput a day picker.
        widget = self.fields["period"].widget
        widget.input_type = "month"
        widget.format = "%Y-%m"
