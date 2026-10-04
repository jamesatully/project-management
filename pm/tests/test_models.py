import datetime
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from ..models import Invoice
from .factories import make_invoice, make_po, make_project, make_vendor


class ProjectModelTests(TestCase):
    def test_uuid_primary_key(self):
        self.assertIsInstance(make_project().pk, uuid.UUID)

    def test_project_id_format_validated(self):
        project = make_project()
        project.project_id = "2021/2/20"
        with self.assertRaises(ValidationError) as ctx:
            project.full_clean()
        self.assertIn("project_id", ctx.exception.message_dict)

    def test_project_id_unique_budget_id_not(self):
        make_project()
        make_project(project_id="2022-1-1-0")  # same budget ID is fine
        with self.assertRaises(IntegrityError):
            make_project(budget_id="1")


class PurchaseOrderModelTests(TestCase):
    def test_end_date_must_follow_start(self):
        po = make_po(start_date=datetime.date(2026, 5, 1), end_date=datetime.date(2026, 4, 1))
        with self.assertRaises(ValidationError):
            po.full_clean()


class InvoiceModelTests(TestCase):
    def test_vendor_must_match_purchase_order(self):
        invoice = make_invoice(make_po())
        invoice.vendor = make_vendor(name="Other Co")
        with self.assertRaises(ValidationError) as ctx:
            invoice.full_clean()
        self.assertIn("purchase_order", ctx.exception.message_dict)

    def test_paid_requires_paid_date(self):
        invoice = make_invoice(make_po(), status=Invoice.Status.PAID)
        with self.assertRaises(ValidationError) as ctx:
            invoice.full_clean()
        self.assertIn("paid_date", ctx.exception.message_dict)

    def test_invoice_number_unique_per_vendor(self):
        po = make_po()
        make_invoice(po)
        with self.assertRaises(IntegrityError):
            make_invoice(po)
