from django.contrib import admin

from .models import ComplianceUnit, Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["name", "primary_contact_name", "primary_contact_phone", "website"]
    search_fields = ["name", "primary_contact_name"]


@admin.register(ComplianceUnit)
class ComplianceUnitAdmin(admin.ModelAdmin):
    list_display = ["name", "unit_type"]
    list_filter = ["unit_type"]
    search_fields = ["name"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["project_id", "name", "budget_id", "project_type", "status", "project_manager"]
    list_filter = ["project_type", "status"]
    search_fields = ["project_id", "name", "budget_id", "project_manager"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["po_number", "vendor", "project", "amount", "status", "start_date", "end_date"]
    list_filter = ["status"]
    search_fields = ["po_number", "contract_number", "vendor__name"]
    autocomplete_fields = ["vendor", "project"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "vendor", "purchase_order", "amount", "status", "invoice_date", "paid_date"]
    list_filter = ["status"]
    search_fields = ["invoice_number", "vendor__name", "purchase_order__po_number"]
    autocomplete_fields = ["vendor", "purchase_order"]


@admin.register(FieldReport)
class FieldReportAdmin(admin.ModelAdmin):
    list_display = ["report_date", "project", "entered_by", "time_on_site"]
    search_fields = ["entered_by", "project__name", "observation_notes"]
    autocomplete_fields = ["project"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["subject", "project", "compliance_unit", "document_type", "document_date"]
    list_filter = ["document_type"]
    search_fields = ["subject", "originating_organization", "recipient_organization"]
    autocomplete_fields = ["project", "compliance_unit", "purchase_order", "invoice"]
