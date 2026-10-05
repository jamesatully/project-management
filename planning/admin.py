from django.contrib import admin

from .models import ActivityNote, CommunicationItem, Milestone, Objective, ProjectPlan, Risk, Stakeholder


class ProjectChildAdmin(admin.ModelAdmin):
    autocomplete_fields = ["project"]
    list_select_related = ["project"]


@admin.register(ProjectPlan)
class ProjectPlanAdmin(ProjectChildAdmin):
    list_display = ["project", "status", "approved_by", "approved_date", "updated_at"]
    list_filter = ["status"]
    search_fields = ["project__name", "project__project_id"]


@admin.register(Objective)
class ObjectiveAdmin(ProjectChildAdmin):
    list_display = ["description", "project", "target_date", "status"]
    list_filter = ["status"]
    search_fields = ["description"]


@admin.register(Risk)
class RiskAdmin(ProjectChildAdmin):
    list_display = ["title", "project", "category", "likelihood", "impact", "score", "status", "owner"]
    list_filter = ["status", "category"]
    search_fields = ["title", "description"]


@admin.register(Stakeholder)
class StakeholderAdmin(ProjectChildAdmin):
    list_display = ["name", "organization", "project", "influence", "interest"]
    search_fields = ["name", "organization"]


@admin.register(Milestone)
class MilestoneAdmin(ProjectChildAdmin):
    list_display = ["name", "project", "planned_date", "forecast_date", "actual_date", "status"]
    list_filter = ["status"]
    search_fields = ["name"]


@admin.register(CommunicationItem)
class CommunicationItemAdmin(ProjectChildAdmin):
    list_display = ["purpose", "audience", "method", "frequency", "project"]
    search_fields = ["purpose", "audience"]


@admin.register(ActivityNote)
class ActivityNoteAdmin(ProjectChildAdmin):
    list_display = ["note_date", "project", "note_type", "period", "author_name", "title"]
    list_filter = ["note_type"]
    search_fields = ["title", "body", "author_name"]
