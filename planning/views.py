"""
Project "Plan" and "Activity" tabs, plus dashboard panels.

Section records (risks, milestones, ...) are created and edited through pm's
generic form views; links here pass ``?project=<id>`` to pre-fill the project
and ``?next=<this page>`` to return here after saving.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils.http import urlencode
from django.views import generic

from pm.models import Project
from pm.resources import REGISTRY
from pm.views import build_table, detail_tabs

from .models import ActivityNote, Risk, previous_month

ACTIVE_STATUSES = [Project.Status.DESIGN, Project.Status.CONSTRUCTION]

# Plan tab sections, in display order: (resource key, related name on Project, heading).
PLAN_SECTIONS = [
    ("objective", "objectives", "Objectives"),
    ("milestone", "milestones", "Milestones"),
    ("risk", "risks", "Risk Register"),
    ("stakeholder", "stakeholders", "Stakeholders"),
    ("communicationitem", "communication_items", "Communication Plan"),
]


def create_url(resource_key, next_url, **initial):
    return f"{reverse(f'pm:{resource_key}-create')}?{urlencode({**initial, 'next': next_url})}"


def monthly_update_url(project, next_url, period=None):
    """Link to a new monthly update for ``project``, pre-filled with last month and the PM's name."""
    period = period or previous_month()
    return create_url(
        "activitynote", next_url, project=project.pk, note_type=ActivityNote.NoteType.MONTHLY,
        period=period.strftime("%Y-%m"), author_name=project.project_manager,
    )


class ProjectTabMixin(LoginRequiredMixin):
    model = Project
    context_object_name = "project"
    tab_url_name = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object
        ctx.update(
            resource=REGISTRY["project"],
            active_nav="project",
            tabs=detail_tabs("project", project, self.tab_url_name),
            back_url=reverse("pm:project-list"),
            here=self.request.path,
        )
        return ctx


class ProjectPlanView(ProjectTabMixin, generic.DetailView):
    template_name = "planning/project_plan.html"
    tab_url_name = "planning:project-plan"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project, here = self.object, self.request.path
        plan = getattr(project, "plan", None)  # the reverse one-to-one raises AttributeError when missing
        ctx["plan"] = plan
        if plan:
            ctx["plan_edit_url"] = f"{reverse('pm:plan-update', args=[plan.pk])}?{urlencode({'next': here})}"
        else:
            ctx["plan_create_url"] = create_url("plan", here, project=project.pk)

        ctx["sections"] = []
        for key, accessor, title in PLAN_SECTIONS:
            table = build_table(REGISTRY[key], getattr(project, accessor).all(), exclude=["project"], limit=50, next_url=here)
            table.update(title=title, add_url=create_url(key, here, project=project.pk), anchor=key)
            ctx["sections"].append(table)
        return ctx


class ProjectActivityView(ProjectTabMixin, generic.DetailView):
    template_name = "planning/project_activity.html"
    tab_url_name = "planning:project-activity"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project, here = self.object, self.request.path
        notes = project.activity_notes.all()
        note_type = self.request.GET.get("type")
        if note_type in ActivityNote.NoteType.values:
            notes = notes.filter(note_type=note_type)
        last_month = previous_month()
        ctx.update(
            notes=notes,
            note_type=note_type,
            note_types=ActivityNote.NoteType.choices,
            last_month=last_month,
            last_month_done=project.activity_notes.filter(
                note_type=ActivityNote.NoteType.MONTHLY, period=last_month
            ).exists(),
            monthly_url=monthly_update_url(project, here, last_month),
            note_url=create_url(
                "activitynote", here, project=project.pk, note_type=ActivityNote.NoteType.GENERAL,
                author_name=project.project_manager,
            ),
            edit_suffix=f"?{urlencode({'next': here})}",
        )
        return ctx


# --- Dashboard panels (registered in planning/resources.py) --------------------


def updates_due_panel(request):
    """Active projects that have no monthly update for last month."""
    period = previous_month()
    missing = (
        Project.objects.filter(status__in=ACTIVE_STATUSES)
        .exclude(activity_notes__note_type=ActivityNote.NoteType.MONTHLY, activity_notes__period=period)
        .order_by("project_manager", "project_id")
    )
    here = reverse("pm:dashboard")
    return {
        "template": "planning/panel_updates_due.html",
        "period": period,
        "count": missing.count(),
        "active_count": Project.objects.filter(status__in=ACTIVE_STATUSES).count(),
        "rows": [{"project": p, "add_url": monthly_update_url(p, here, period)} for p in missing[:8]],
        "all_url": f"{reverse('pm:project-list')}?{urlencode({'status': Project.Status.CONSTRUCTION})}",
    }


def top_risks_panel(request):
    """Highest-scoring risks that are still open."""
    risks = Risk.objects.exclude(status=Risk.Status.CLOSED).select_related("project").order_by("-score", "-impact")
    return {
        "template": "planning/panel_top_risks.html",
        "risks": risks[:6],
        "open_count": risks.count(),
        "high_count": risks.filter(score__gte=15).count(),
        "all_url": f"{reverse('pm:risk-list')}?{urlencode({'status': Risk.Status.OPEN, 'o': '-score'})}",
    }
