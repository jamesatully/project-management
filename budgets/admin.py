from django.contrib import admin

from .models import Budget, BudgetAmount, BudgetLineItem


class BudgetLineItemInline(admin.TabularInline):
    model = BudgetLineItem
    extra = 0
    show_change_link = True


class BudgetAmountInline(admin.TabularInline):
    model = BudgetAmount
    extra = 0


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["__str__", "project", "budget_year", "status", "approved_date", "updated_at"]
    list_filter = ["status", "budget_year", "project__project_type"]
    list_select_related = ["project"]
    search_fields = ["project__name", "project__project_id", "notes"]
    autocomplete_fields = ["project"]
    readonly_fields = ["superseded_by"]
    inlines = [BudgetLineItemInline]


@admin.register(BudgetLineItem)
class BudgetLineItemAdmin(admin.ModelAdmin):
    list_display = ["__str__", "budget", "category"]
    list_filter = ["category"]
    list_select_related = ["budget__project"]
    search_fields = ["description", "budget__project__name", "budget__project__project_id"]
    raw_id_fields = ["budget"]
    inlines = [BudgetAmountInline]
