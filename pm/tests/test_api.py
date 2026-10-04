from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from ..models import Project
from .factories import make_document, make_field_report, make_invoice, make_po, make_project, make_vendor


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
        for endpoint in ["projects", "vendors", "purchase-orders", "invoices", "field-reports", "documents"]:
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
                "project_type": "ENVIRONMENTAL",
                "status": "DESIGN",
                "project_manager": "Alex Doe",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["project_type_display"], "Environmental")
        self.assertTrue(Project.objects.filter(project_id="2024-3-1-0").exists())

    def test_invalid_project_id_rejected(self):
        response = self.client.post(
            "/api/projects/",
            {"name": "X", "project_id": "bad", "budget_id": "1", "project_type": "CIP", "project_manager": "Y"},
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

    def test_schema_available(self):
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
