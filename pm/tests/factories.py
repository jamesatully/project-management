"""Minimal object builders for tests (kept dependency-free)."""
import datetime
from decimal import Decimal

from ..models import ComplianceUnit, Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor


def make_vendor(**kw):
    return Vendor.objects.create(**{"name": "Acme Paving", **kw})


def make_project(**kw):
    defaults = {
        "name": "Main St Rehab",
        "project_id": "2021-2-20-0",
        "budget_id": "6822015",
        "project_type": Project.ProjectType.CIP_RR,
        "project_manager": "Pat Example",
    }
    return Project.objects.create(**{**defaults, **kw})


def make_compliance_unit(**kw):
    defaults = {"name": "Northwest Wastewater Treatment System", "unit_type": ComplianceUnit.UnitType.WASTEWATER}
    return ComplianceUnit.objects.create(**{**defaults, **kw})


def make_po(vendor=None, project=None, **kw):
    defaults = {"po_number": "4500001", "amount": Decimal("100000.00"), "status": PurchaseOrder.Status.OPEN}
    return PurchaseOrder.objects.create(vendor=vendor or make_vendor(), project=project, **{**defaults, **kw})


def make_invoice(po, **kw):
    defaults = {"invoice_number": "INV-1", "amount": Decimal("2500.00"), "invoice_date": datetime.date(2026, 1, 15)}
    return Invoice.objects.create(vendor=po.vendor, purchase_order=po, **{**defaults, **kw})


def make_field_report(project, **kw):
    defaults = {"entered_by": "Sam Inspector", "report_date": datetime.date(2026, 2, 1), "time_on_site": Decimal("3.5")}
    return FieldReport.objects.create(project=project, **{**defaults, **kw})


def make_document(project=None, **kw):
    defaults = {
        "subject": "Notice to proceed",
        "originating_organization": "City",
        "recipient_organization": "Acme Paving",
        "document_type": Document.DocumentType.LETTER,
        "document_date": datetime.date(2026, 1, 5),
    }
    return Document.objects.create(project=project, **{**defaults, **kw})
