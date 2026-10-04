from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Project, Vendor
from ..resources import REGISTRY
from .factories import make_document, make_field_report, make_invoice, make_po, make_project, make_vendor


class ViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_login(self.user)
        self.project = make_project()
        self.po = make_po(project=self.project)
        self.objects = {
            "project": self.project,
            "vendor": self.po.vendor,
            "purchaseorder": self.po,
            "invoice": make_invoice(self.po),
            "fieldreport": make_field_report(self.project),
            "document": make_document(self.project),
        }

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("pm:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_dashboard(self):
        response = self.client.get(reverse("pm:dashboard"))
        self.assertContains(response, "Invoiced vs. committed")
        self.assertContains(response, self.project.name)

    def test_all_resource_pages_render(self):
        for key, obj in self.objects.items():
            for name, args in [("list", []), ("create", []), ("detail", [obj.pk]), ("update", [obj.pk]), ("delete", [obj.pk])]:
                with self.subTest(resource=key, view=name):
                    response = self.client.get(reverse(f"pm:{key}-{name}", args=args))
                    self.assertEqual(response.status_code, 200)
        self.assertEqual(set(self.objects), set(REGISTRY))

    def test_list_search_filter_and_sort(self):
        make_project(project_id="2023-1-1-0", name="Harbor Dredging", status="COMPLETE")
        url = reverse("pm:project-list")
        self.assertContains(self.client.get(url, {"q": "harbor"}), "Harbor Dredging")
        self.assertNotContains(self.client.get(url, {"q": "harbor"}), "Main St Rehab")
        self.assertNotContains(self.client.get(url, {"status": "COMPLETE"}), "Main St Rehab")
        self.assertEqual(self.client.get(url, {"o": "-name"}).status_code, 200)

    def test_create_project_via_form(self):
        response = self.client.post(
            reverse("pm:project-create"),
            {
                "name": "Bridge Retrofit",
                "project_id": "2025-4-2-1",
                "budget_id": "7000001",
                "project_type": "CIP",
                "status": "PLANNING",
                "project_manager": "Jo Smith",
            },
        )
        project = Project.objects.get(project_id="2025-4-2-1")
        self.assertRedirects(response, project.get_absolute_url())

    def test_create_prefills_from_querystring(self):
        response = self.client.get(reverse("pm:fieldreport-create"), {"project": self.project.pk})
        self.assertEqual(str(response.context["form"].initial["project"]), str(self.project.pk))

    def test_protected_delete_shows_error(self):
        vendor = self.po.vendor
        response = self.client.post(reverse("pm:vendor-delete", args=[vendor.pk]), follow=True)
        self.assertTrue(Vendor.objects.filter(pk=vendor.pk).exists())
        self.assertContains(response, "be deleted because other records reference it")

    def test_delete(self):
        vendor = make_vendor(name="Unused Vendor")
        self.client.post(reverse("pm:vendor-delete", args=[vendor.pk]))
        self.assertFalse(Vendor.objects.filter(pk=vendor.pk).exists())
