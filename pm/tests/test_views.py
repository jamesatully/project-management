from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Contact, Project, Vendor
from ..resources import REGISTRY
from .factories import (
    make_compliance_unit, make_contact, make_document, make_field_report, make_invoice, make_po, make_project,
    make_vendor,
)


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
            "complianceunit": make_compliance_unit(),
            "contact": make_contact(user=self.user, email="jordan@agency.example"),
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
        pm_resources = {key for key, r in REGISTRY.items() if r.model._meta.app_label == "pm"}
        self.assertEqual(set(self.objects), pm_resources)

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
                "project_type": "CIP_RR",
                "status": "PLANNING",
                "project_manager": "Jo Smith",
            },
        )
        project = Project.objects.get(project_id="2025-4-2-1")
        self.assertRedirects(response, project.get_absolute_url())

    def test_create_prefills_from_querystring(self):
        response = self.client.get(reverse("pm:fieldreport-create"), {"project": self.project.pk})
        self.assertEqual(str(response.context["form"].initial["project"]), str(self.project.pk))

    def test_compliance_unit_page_lists_documents(self):
        unit = self.objects["complianceunit"]
        make_document(compliance_unit=unit, subject="Discharge Monitoring Report — August 2026")
        response = self.client.get(unit.get_absolute_url())
        self.assertContains(response, "Discharge Monitoring Report — August 2026")
        self.assertContains(response, f"/documents/new/?compliance_unit={unit.pk}")

    def test_document_list_filters_by_invoice(self):
        invoice = self.objects["invoice"]
        make_document(invoice=invoice, subject="Invoice returned")
        response = self.client.get(reverse("pm:document-list"), {"invoice": invoice.pk})
        self.assertContains(response, "Invoice returned")
        self.assertNotContains(response, "Notice to proceed")

    def test_document_form_requires_a_link(self):
        response = self.client.post(reverse("pm:document-create"), {
            "subject": "Orphan", "document_type": "LETTER", "document_date": "2026-01-05",
            "originating_organization": "A", "recipient_organization": "B",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link the document to at least one")

    def test_protected_delete_shows_error(self):
        vendor = self.po.vendor
        response = self.client.post(reverse("pm:vendor-delete", args=[vendor.pk]), follow=True)
        self.assertTrue(Vendor.objects.filter(pk=vendor.pk).exists())
        self.assertContains(response, "be deleted because other records reference it")

    def test_delete(self):
        vendor = make_vendor(name="Unused Vendor")
        self.client.post(reverse("pm:vendor-delete", args=[vendor.pk]))
        self.assertFalse(Vendor.objects.filter(pk=vendor.pk).exists())


class ContactViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_login(self.user)
        self.staff = make_contact(name="Dana Staff", organization="Utility", contact_type="INTERNAL", user=self.user)
        self.outside = make_contact(name="Robin Regulator", email="robin@agency.example")

    def test_detail_shows_user_and_email(self):
        response = self.client.get(self.staff.get_absolute_url())
        self.assertContains(response, "tester")  # linked account, shown as plain text (users have no page)
        response = self.client.get(self.outside.get_absolute_url())
        self.assertContains(response, 'href="mailto:robin@agency.example"')

    def test_list_filters(self):
        url = reverse("pm:contact-list")
        self.assertContains(self.client.get(url), "Contacts")
        response = self.client.get(url, {"contact_type": "INTERNAL"})
        self.assertContains(response, "Dana Staff")
        self.assertNotContains(response, "Robin Regulator")
        response = self.client.get(url, {"has_user": "false"})
        self.assertContains(response, "Robin Regulator")
        self.assertNotContains(response, "Dana Staff")
        self.assertContains(self.client.get(url, {"q": "regulator"}), "Robin Regulator")

    def test_create_contact_without_user(self):
        response = self.client.post(reverse("pm:contact-create"), {
            "name": "Casey Neighbor", "organization": "Northside Neighborhood Association", "contact_type": "EXTERNAL",
        })
        contact = Contact.objects.get(name="Casey Neighbor")
        self.assertRedirects(response, contact.get_absolute_url())
        self.assertIsNone(contact.user)

    def test_user_can_only_link_to_one_contact(self):
        response = self.client.post(reverse("pm:contact-create"), {
            "name": "Someone Else", "contact_type": "INTERNAL", "user": self.user.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
