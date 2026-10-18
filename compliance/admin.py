from django.contrib import admin

from .models import ComplianceMilestone, Permit


class ComplianceMilestoneInline(admin.TabularInline):
    model = ComplianceMilestone
    extra = 0
    fields = ["name", "permit_condition", "due_date", "status", "submitted_date"]
    show_change_link = True


@admin.register(Permit)
class PermitAdmin(admin.ModelAdmin):
    list_display = ["name", "permit_number", "compliance_unit", "issuing_agency", "status", "expiration_date"]
    list_filter = ["status", "compliance_unit__unit_type"]
    list_select_related = ["compliance_unit"]
    search_fields = ["name", "permit_number", "issuing_agency", "compliance_unit__name"]
    inlines = [ComplianceMilestoneInline]


@admin.register(ComplianceMilestone)
class ComplianceMilestoneAdmin(admin.ModelAdmin):
    list_display = ["name", "permit", "permit_condition", "due_date", "target_date", "status", "submitted_date", "manager"]
    list_filter = ["status", "permit__compliance_unit"]
    list_select_related = ["permit", "manager"]
    search_fields = ["name", "permit_condition", "description", "permit__name"]
    raw_id_fields = ["permit", "manager", "submittal_document"]
    date_hierarchy = "due_date"
