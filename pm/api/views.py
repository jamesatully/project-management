"""
REST API viewsets. Every resource supports list / retrieve / create /
update / partial update / delete, plus ``?search=``, ``?ordering=`` and the
field filters defined in :mod:`pm.filters`.
"""
from rest_framework import viewsets
from rest_framework.decorators import action

from .. import filters
from ..models import ComplianceUnit, Contact, Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor
from ..views import document_file_response
from . import serializers


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = serializers.VendorSerializer
    filterset_class = filters.VendorFilter
    search_fields = ["name", "primary_contact_name", "mailing_address"]
    ordering_fields = ["name", "created_at"]


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related("user")
    serializer_class = serializers.ContactSerializer
    filterset_class = filters.ContactFilter
    search_fields = ["name", "title", "organization", "role_description", "email"]
    ordering_fields = ["name", "organization", "contact_type", "created_at"]


class ComplianceUnitViewSet(viewsets.ModelViewSet):
    queryset = ComplianceUnit.objects.all()
    serializer_class = serializers.ComplianceUnitSerializer
    filterset_class = filters.ComplianceUnitFilter
    search_fields = ["name"]
    ordering_fields = ["name", "unit_type"]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.select_related("project_manager")
    serializer_class = serializers.ProjectSerializer
    filterset_class = filters.ProjectFilter
    search_fields = ["name", "project_id", "budget_id", "project_manager__name"]
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

    @action(detail=True, url_path="file", url_name="file")
    def download(self, request, pk=None):
        """The document's uploaded file, inline under its original name (404 if it has none)."""
        return document_file_response(self.get_object())
