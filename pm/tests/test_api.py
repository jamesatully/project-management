from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from ..models import Project
from .factories import (
    make_compliance_unit, make_contact, make_document, make_field_report, make_invoice, make_po, make_project,
    make_project_manager, make_vendor,
)


class APITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_authenticate(self.user)
        self.project = make_project()
        self.vendor = make_vendor()
        self.po = make_po(vendor=self.vendor, project=self.project)

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/projects/").status_code, 401)

    def test_every_endpoint_lists(self):
        make_invoice(self.po)
        make_field_report(self.project)
        make_document(self.project)
        make_compliance_unit()
        # The one contact is the project's manager.
        for endpoint in ["projects", "vendors", "compliance-units", "purchase-orders", "invoices", "field-reports",
                         "documents", "contacts"]:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/api/{endpoint}/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)

    def test_create_project(self):
        response = self.client.post(
            "/api/projects/",
            {
                "name": "Creek Restoration",
                "project_id": "2024-3-1-0",
                "budget_id": "6822015",
                "project_type": "CIP_EXPANSION",
                "status": "DESIGN",
                "project_manager": make_project_manager("Alex Doe").pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["project_type_display"], "CIP Expansion")
        self.assertTrue(Project.objects.filter(project_id="2024-3-1-0").exists())

    def test_invalid_project_id_rejected(self):
        response = self.client.post(
            "/api/projects/",
            {"name": "X", "project_id": "bad", "budget_id": "1", "project_type": "CIP_RR",
             "project_manager": make_project_manager().pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("project_id", response.data)

    def test_invoice_vendor_mismatch_rejected(self):
        other = make_vendor(name="Other Co")
        response = self.client.post(
            "/api/invoices/",
            {
                "invoice_number": "A-1",
                "vendor": other.pk,
                "purchase_order": self.po.pk,
                "amount": "10.00",
                "invoice_date": "2026-03-01",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("purchase_order", response.data)

    def test_filter_and_search(self):
        make_project(project_id="2022-1-1-0", name="Sewer Upgrade", status="COMPLETE")
        self.assertEqual(self.client.get("/api/projects/?status=COMPLETE").data["count"], 1)
        self.assertEqual(self.client.get("/api/projects/?search=sewer").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/invoices/?project={self.project.pk}").data["count"], 0)

    def test_project_manager(self):
        data = self.client.get(f"/api/projects/{self.project.pk}/").data
        self.assertEqual(data["project_manager"], self.project.project_manager.pk)
        self.assertEqual(data["project_manager_name"], "Pat Example")

        other = make_project_manager("Robin Planner")
        make_project(project_id="2022-1-1-0", project_manager=other)
        self.assertEqual(self.client.get(f"/api/projects/?project_manager={other.pk}").data["count"], 1)
        self.assertEqual(self.client.get("/api/projects/?search=robin").data["count"], 1)

    def test_external_project_manager_rejected(self):
        response = self.client.patch(f"/api/projects/{self.project.pk}/", {"project_manager": make_contact().pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("project_manager", response.data)

    def test_removed_project_type_rejected(self):
        response = self.client.post(
            "/api/projects/",
            {"name": "X", "project_id": "2024-1-1-0", "budget_id": "1", "project_type": "ENVIRONMENTAL",
             "project_manager": make_project_manager().pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("project_type", response.data)

    def test_document_needs_a_link(self):
        base = {"subject": "Annual report", "originating_organization": "Utility", "recipient_organization": "DEQ",
                "document_type": "REPORT", "document_date": "2026-02-01"}
        response = self.client.post("/api/documents/", base)
        self.assertEqual(response.status_code, 400)
        self.assertIn("at least one", str(response.data))

        unit = make_compliance_unit()
        response = self.client.post("/api/documents/", {**base, "compliance_unit": unit.pk})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["compliance_unit_name"], unit.name)
        self.assertIsNone(response.data["project"])
        self.assertEqual(self.client.get(f"/api/documents/?compliance_unit={unit.pk}").data["count"], 1)

        invoice = make_invoice(self.po)
        response = self.client.post(
            "/api/documents/", {**base, "invoice": invoice.pk, "purchase_order": self.po.pk, "project": self.project.pk}
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get(f"/api/documents/?invoice={invoice.pk}").data["count"], 1)

    def test_contacts_with_and_without_user(self):
        response = self.client.post("/api/contacts/", {
            "name": "Dana Staff", "organization": "Utility", "contact_type": "INTERNAL", "user": self.user.pk,
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["username"], "tester")
        self.assertEqual(response.data["contact_type_display"], "Internal")
        response = self.client.post("/api/contacts/", {"name": "Robin Regulator", "organization": "State DEQ"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["contact_type"], "EXTERNAL")  # the default
        self.assertIsNone(response.data["user"])
        self.assertEqual(self.client.get("/api/contacts/?has_user=true").data["count"], 1)
        self.assertEqual(self.client.get("/api/contacts/?contact_type=EXTERNAL").data["count"], 1)
        self.assertEqual(self.client.get("/api/contacts/?search=deq").data["count"], 1)
        # A user account can belong to only one contact.
        response = self.client.post("/api/contacts/", {"name": "Someone", "user": self.user.pk})
        self.assertEqual(response.status_code, 400)

    def test_schema_available(self):
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
