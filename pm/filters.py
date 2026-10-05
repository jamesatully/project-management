"""
FilterSets shared by the REST API and the web UI list views, so filtering
behaves identically in both places.
"""
import django_filters
from django import forms

from .models import ComplianceUnit, Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor


class ProjectFilter(django_filters.FilterSet):
    class Meta:
        model = Project
        fields = ["status", "project_type", "budget_id"]


class VendorFilter(django_filters.FilterSet):
    class Meta:
        model = Vendor
        fields = []


class ComplianceUnitFilter(django_filters.FilterSet):
    class Meta:
        model = ComplianceUnit
        fields = ["unit_type"]


class PurchaseOrderFilter(django_filters.FilterSet):
    start_date_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte", label="Starts after")
    end_date_before = django_filters.DateFilter(field_name="end_date", lookup_expr="lte", label="Ends before")

    class Meta:
        model = PurchaseOrder
        fields = ["status", "vendor", "project"]


class InvoiceFilter(django_filters.FilterSet):
    invoice_date_after = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte", label="From")
    invoice_date_before = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte", label="To")
    project = django_filters.ModelChoiceFilter(
        field_name="purchase_order__project", queryset=Project.objects.all(), label="Project"
    )

    class Meta:
        model = Invoice
        fields = ["status", "vendor", "purchase_order"]


class FieldReportFilter(django_filters.FilterSet):
    report_date_after = django_filters.DateFilter(field_name="report_date", lookup_expr="gte", label="From")
    report_date_before = django_filters.DateFilter(field_name="report_date", lookup_expr="lte", label="To")

    class Meta:
        model = FieldReport
        fields = ["project"]


class DocumentFilter(django_filters.FilterSet):
    document_date_after = django_filters.DateFilter(field_name="document_date", lookup_expr="gte", label="From")
    document_date_before = django_filters.DateFilter(field_name="document_date", lookup_expr="lte", label="To")
    # Thousands of invoices and hundreds of POs are too many for a dropdown; these accept a UUID
    # (used by "View all" links on PO and invoice pages) and render as hidden inputs in the filter bar.
    purchase_order = django_filters.UUIDFilter(widget=forms.HiddenInput)
    invoice = django_filters.UUIDFilter(widget=forms.HiddenInput)

    class Meta:
        model = Document
        fields = ["project", "compliance_unit", "document_type", "purchase_order", "invoice"]
