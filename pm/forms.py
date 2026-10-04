"""
ModelForms for data entry. :class:`StyledModelForm` applies the Tailwind
classes used throughout the UI and renders dates with the native date picker.
"""
from django import forms

from .models import Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor

INPUT_CLASSES = (
    "w-full rounded-lg border border-stroke bg-transparent px-4 py-2.5 text-sm text-ink "
    "outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 "
    "dark:border-strokedark dark:bg-boxdark-2 dark:text-white"
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
                widget.format = "%Y-%m-%d"
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 4)
            widget.attrs["class"] = INPUT_CLASSES


class ProjectForm(StyledModelForm):
    class Meta:
        model = Project
        fields = ["name", "project_id", "budget_id", "project_type", "status", "project_manager"]
        widgets = {"project_id": forms.TextInput(attrs={"placeholder": "2021-2-20-0"})}


class VendorForm(StyledModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "mailing_address", "website", "primary_contact_name", "primary_contact_phone"]
        widgets = {"mailing_address": forms.Textarea(attrs={"rows": 3})}


class PurchaseOrderForm(StyledModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["po_number", "status", "amount", "vendor", "project", "contract_number", "start_date", "end_date"]


class InvoiceForm(StyledModelForm):
    class Meta:
        model = Invoice
        fields = [
            "invoice_number", "vendor", "purchase_order", "status", "amount",
            "invoice_date", "received_date", "paid_date",
        ]


class FieldReportForm(StyledModelForm):
    class Meta:
        model = FieldReport
        fields = [
            "project", "entered_by", "report_date", "data_entry_date", "time_on_site",
            "observation_notes", "safety_notes", "weather_notes",
        ]


class DocumentForm(StyledModelForm):
    class Meta:
        model = Document
        fields = [
            "project", "subject", "document_type", "document_date",
            "originating_organization", "recipient_organization",
        ]
