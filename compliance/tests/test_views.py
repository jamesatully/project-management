import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from pm.models import ComplianceUnit
from pm.tests.factories import make_compliance_unit, make_document, make_project

from ..forms import ComplianceMilestoneForm
from ..models import ComplianceMilestone
from .factories import make_compliance_manager, make_milestone, make_permit

S = ComplianceMilestone.Status
TODAY = datetime.date(2026, 7, 10)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class ComplianceViewTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("tester", password="pw-123456!"))
        self.unit = make_compliance_unit()
        self.permit = make_permit(self.unit)
        self.doc = make_document(compliance_unit=self.unit, subject="DMR — May 2026 submittal")
        self.overdue = make_milestone(self.permit, name="Corrective Action Plan", due_date=datetime.date(2026, 7, 1))
        self.done = make_milestone(self.permit, status=S.SUBMITTED, submitted_date=datetime.date(2026, 6, 30),
                                   submittal_document=self.doc)

    def test_lists_and_sidebar(self, _today):
        response = self.client.get(reverse("pm:compliancemilestone-list"))
        self.assertContains(response, "Corrective Action Plan")
        self.assertContains(response, "Overdue")
        self.assertContains(response, reverse("pm:permit-list"))  # sidebar
        response = self.client.get(reverse("pm:compliancemilestone-list"), {"status": "OVERDUE"})
        self.assertEqual(list(response.context["object_list"]), [self.overdue])
        response = self.client.get(reverse("pm:permit-list"))
        self.assertContains(response, "Riverbend WWTP NPDES Permit")
        self.assertContains(response, "Jul 1, 2026")  # next due: the overdue milestone

    def test_detail_pages_show_related_records(self, _today):
        # Compliance unit -> permits; permit -> milestones; contact and document -> milestones.
        self.assertContains(self.client.get(self.unit.get_absolute_url()), self.permit.name)
        response = self.client.get(self.permit.get_absolute_url())
        self.assertContains(response, "Corrective Action Plan")
        self.assertContains(response, f"{reverse('pm:compliancemilestone-create')}?permit={self.permit.pk}")
        contact_page = self.client.get(self.overdue.manager.get_absolute_url())
        self.assertContains(contact_page, "Corrective Action Plan")  # milestones they manage
        self.assertContains(contact_page, self.permit.name)  # permits they manage
        self.assertContains(self.client.get(self.doc.get_absolute_url()), self.done.name)

    def test_milestone_detail_shows_derived_status_and_variance(self, _today):
        response = self.client.get(self.overdue.get_absolute_url())
        self.assertContains(response, "Overdue")
        response = self.client.get(self.done.get_absolute_url())
        self.assertContains(response, "Submitted vs. due")
        self.assertContains(response, "2 days late")
        self.assertContains(response, "DMR — May 2026 submittal")

    def test_dashboard_panel(self, _today):
        make_milestone(self.permit, name="Annual Pretreatment Report", due_date=datetime.date(2026, 8, 1))
        make_milestone(self.permit, name="Far off", due_date=datetime.date(2026, 12, 1))
        response = self.client.get(reverse("pm:dashboard"))
        self.assertContains(response, "Compliance deadlines")
        self.assertContains(response, "1 overdue")
        self.assertContains(response, "1 due in the next 30 days")
        self.assertContains(response, "Annual Pretreatment Report")
        self.assertNotContains(response, "Far off")

    def test_create_from_permit_page(self, _today):
        here = self.permit.get_absolute_url()
        url = f"{reverse('pm:compliancemilestone-create')}?permit={self.permit.pk}&next={here}"
        self.assertEqual(self.client.get(url).context["form"].initial["permit"], str(self.permit.pk))
        response = self.client.post(url, {
            "permit": self.permit.pk, "name": "DMR — June 2026", "permit_condition": "S1.A",
            "manager": make_compliance_manager().pk, "status": S.NOT_STARTED, "due_date": "2026-07-28",
            "target_date": "2026-07-21",
        })
        self.assertRedirects(response, here)
        self.assertTrue(ComplianceMilestone.objects.filter(name="DMR — June 2026").exists())

    def test_document_choices_narrow_to_the_permits_unit(self, _today):
        other_unit = make_compliance_unit(name="North Fork PWS", unit_type=ComplianceUnit.UnitType.PUBLIC_WATER_SUPPLY)
        other_permit = make_permit(other_unit, name="North Fork PWS Operating Permit")
        other_doc = make_document(compliance_unit=other_unit, subject="MOR — May 2026")
        make_document(project=make_project(), subject="Project letter")  # not filed under a unit: never offered

        def choices(form):
            return set(form.fields["submittal_document"].queryset)

        self.assertEqual(choices(ComplianceMilestoneForm()), {self.doc, other_doc})
        self.assertEqual(choices(ComplianceMilestoneForm(initial={"permit": str(self.permit.pk)})), {self.doc})
        self.assertEqual(choices(ComplianceMilestoneForm(instance=self.done)), {self.doc})
        self.assertEqual(choices(ComplianceMilestoneForm(data={"permit": other_permit.pk})), {other_doc})
        self.assertEqual(choices(ComplianceMilestoneForm(data={"permit": "not-a-uuid"})), {self.doc, other_doc})
