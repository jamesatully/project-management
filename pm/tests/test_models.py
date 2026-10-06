import datetime
import importlib
import uuid

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from ..models import Document, Invoice, Project
from .factories import make_compliance_unit, make_document, make_invoice, make_po, make_project, make_vendor


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


class ProjectTypeTests(TestCase):
    def test_project_types(self):
        self.assertEqual(
            Project.ProjectType.choices,
            [("CIP_EXPANSION", "CIP Expansion"), ("CIP_RR", "CIP R&R"), ("DEVELOPMENT", "Development")],
        )


class ProjectTypeMigrationTests(TestCase):
    def test_old_types_map_to_cip_rr(self):
        migration = importlib.import_module("pm.migrations.0002_compliance_units_and_document_links")
        old_cip, old_env = make_project(), make_project(project_id="2022-1-1-0")
        Project.objects.filter(pk=old_cip.pk).update(project_type="CIP")
        Project.objects.filter(pk=old_env.pk).update(project_type="ENVIRONMENTAL")
        migration.remap_project_types(migration.FORWARD)(apps, None)
        self.assertEqual(set(Project.objects.values_list("project_type", flat=True)), {"CIP_RR"})


class DocumentLinkTests(TestCase):
    def doc(self, **links):
        return Document(subject="Letter", originating_organization="A", recipient_organization="B",
                        document_type="LETTER", document_date=datetime.date(2026, 1, 1), **links)

    def test_document_requires_at_least_one_link(self):
        with self.assertRaises(ValidationError):
            self.doc().full_clean()
        with self.assertRaises(IntegrityError):  # enforced by the database too
            self.doc().save()

    def test_document_can_link_to_any_record(self):
        project, unit = make_project(), make_compliance_unit()
        po = make_po(project=project)
        invoice = make_invoice(po)
        for links in [{"project": project}, {"compliance_unit": unit}, {"purchase_order": po}, {"invoice": invoice}]:
            with self.subTest(links=list(links)):
                self.doc(**links).full_clean()
        doc = self.doc(project=project, invoice=invoice)
        self.assertEqual(doc.linked_records, [project, invoice])

    def test_linked_records_protect_documents(self):
        unit = make_compliance_unit()
        make_document(compliance_unit=unit)
        with self.assertRaises(ProtectedError):
            unit.delete()


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
