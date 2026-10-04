"""
DRF serializers. Foreign keys are written as UUIDs; each read response also
includes a human-readable ``*_display`` / ``*_name`` field for convenience.
Model ``clean()`` validation is applied so the API enforces the same business
rules as the web forms.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from ..models import Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor


class ModelCleanMixin:
    """Run the model's ``clean()`` so API writes get the same validation as forms."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance or self.Meta.model()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(serializers.as_serializer_error(exc))
        return attrs


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id", "name", "mailing_address", "website",
            "primary_contact_name", "primary_contact_phone",
            "created_at", "updated_at",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    project_type_display = serializers.CharField(source="get_project_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "name", "project_id", "budget_id",
            "project_type", "project_type_display", "status", "status_display",
            "project_manager", "created_at", "updated_at",
        ]


class PurchaseOrderSerializer(ModelCleanMixin, serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    project_display = serializers.CharField(source="project", read_only=True, default=None)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "status", "status_display", "amount",
            "vendor", "vendor_name", "project", "project_display",
            "contract_number", "start_date", "end_date",
            "created_at", "updated_at",
        ]


class InvoiceSerializer(ModelCleanMixin, serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "vendor", "vendor_name", "status", "status_display",
            "purchase_order", "po_number", "amount",
            "invoice_date", "received_date", "paid_date",
            "created_at", "updated_at",
        ]


class FieldReportSerializer(serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)

    class Meta:
        model = FieldReport
        fields = [
            "id", "project", "project_display", "entered_by",
            "report_date", "data_entry_date", "time_on_site",
            "observation_notes", "safety_notes", "weather_notes",
            "created_at", "updated_at",
        ]


class DocumentSerializer(serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id", "project", "project_display", "subject",
            "originating_organization", "recipient_organization",
            "document_type", "document_type_display", "document_date",
            "added_date", "last_edited_date",
        ]
        read_only_fields = ["added_date", "last_edited_date"]
