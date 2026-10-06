"""
REST API viewsets. Every resource supports list / retrieve / create /
update / partial update / delete, plus ``?search=``, ``?ordering=`` and the
field filters defined in :mod:`pm.filters`.
"""
from rest_framework import viewsets

from .. import filters
from ..models import ComplianceUnit, Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor
from . import serializers


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = serializers.VendorSerializer
    filterset_class = filters.VendorFilter
    search_fields = ["name", "primary_contact_name", "mailing_address"]
    ordering_fields = ["name", "created_at"]


class ComplianceUnitViewSet(viewsets.ModelViewSet):
    queryset = ComplianceUnit.objects.all()
    serializer_class = serializers.ComplianceUnitSerializer
    filterset_class = filters.ComplianceUnitFilter
    search_fields = ["name"]
    ordering_fields = ["name", "unit_type"]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer
    filterset_class = filters.ProjectFilter
    search_fields = ["name", "project_id", "budget_id", "project_manager"]
    ordering_fields = ["name", "project_id", "budget_id", "status", "created_at"]


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related("vendor", "project")
    serializer_class = serializers.PurchaseOrderSerializer
    filterset_class = filters.PurchaseOrderFilter
    search_fields = ["po_number", "contract_number", "vendor__name", "project__name", "project__project_id"]
    ordering_fields = ["po_number", "amount", "start_date", "end_date", "status"]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related("vendor", "purchase_order")
    serializer_class = serializers.InvoiceSerializer
    filterset_class = filters.InvoiceFilter
    search_fields = ["invoice_number", "vendor__name", "purchase_order__po_number"]
    ordering_fields = ["invoice_number", "amount", "invoice_date", "received_date", "paid_date", "status"]


class FieldReportViewSet(viewsets.ModelViewSet):
    queryset = FieldReport.objects.select_related("project")
    serializer_class = serializers.FieldReportSerializer
    filterset_class = filters.FieldReportFilter
    search_fields = ["entered_by", "observation_notes", "safety_notes", "weather_notes", "project__name"]
    ordering_fields = ["report_date", "data_entry_date", "time_on_site"]


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related("project", "compliance_unit", "purchase_order", "invoice")
    serializer_class = serializers.DocumentSerializer
    filterset_class = filters.DocumentFilter
    search_fields = [
        "subject", "originating_organization", "recipient_organization", "project__name", "compliance_unit__name",
        "purchase_order__po_number", "invoice__invoice_number",
    ]
    ordering_fields = ["document_date", "added_date", "last_edited_date", "document_type"]
