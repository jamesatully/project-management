import datetime
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from ..models import Contact, Invoice, Project, PurchaseOrder, Vendor


class SeedDemoTests(TestCase):
    def seed(self, *args):
        call_command("seed_demo", "--projects", "15", "--today", "2026-06-30", *args, stdout=StringIO())

    def test_seed_creates_valid_related_data(self):
        self.seed()
        self.assertEqual(Vendor.objects.count(), 50)
        self.assertGreaterEqual(Project.objects.count(), 12)
        self.assertTrue(PurchaseOrder.objects.filter(project__isnull=True).exists())  # blanket POs
        for invoice in Invoice.objects.select_related("purchase_order")[:200]:
            self.assertEqual(invoice.vendor_id, invoice.purchase_order.vendor_id)
            self.assertLessEqual(invoice.invoice_date, datetime.date(2026, 6, 30))
            if invoice.status == Invoice.Status.PAID:
                self.assertIsNotNone(invoice.paid_date)
        # Every vendor's primary contact is in the contact directory, alongside utility staff.
        for vendor in Vendor.objects.all():
            self.assertTrue(Contact.objects.filter(name=vendor.primary_contact_name, organization=vendor.name).exists())
        self.assertTrue(Contact.objects.filter(contact_type="INTERNAL", title="Project Manager").exists())
        self.assertFalse(Contact.objects.filter(email__isnull=False).exclude(email="").exclude(email__endswith=".example").exists())

    def test_refuses_to_overwrite_without_flush(self):
        self.seed()
        with self.assertRaises(CommandError):
            self.seed()
        self.seed("--flush")

    def test_deterministic(self):
        self.seed()
        first = sorted(Project.objects.values_list("project_id", "name"))
        self.seed("--flush")
        self.assertEqual(first, sorted(Project.objects.values_list("project_id", "name")))
