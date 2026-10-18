import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from pm.tests.factories import make_compliance_unit, make_contact

from ..models import ComplianceMilestone
from .factories import make_compliance_manager, make_milestone, make_permit

S = ComplianceMilestone.Status
TODAY = datetime.date(2026, 7, 10)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class ComplianceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("api", password="pw-123456!"))
        self.unit = make_compliance_unit()
        self.permit = make_permit(self.unit)
        self.manager = make_compliance_manager()

    def payload(self, **kw):
        return {"permit": str(self.permit.pk), "manager": str(self.manager.pk), "name": "DMR — June 2026",
                "permit_condition": "S1.A", "due_date": "2026-07-28", "target_date": "2026-07-21", **kw}

    def test_create_permit_and_milestone(self, _today):
        response = self.client.post("/api/permits/", {
            "compliance_unit": str(self.unit.pk), "name": "Eastgate NPDES", "issuing_agency": "State DEQ",
            "manager": str(self.manager.pk), "effective_date": "2024-01-01", "expiration_date": "2028-12-31",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["compliance_unit_name"], self.unit.name)
        self.assertEqual(response.data["manager_name"], self.manager.name)
        response = self.client.get(f"/api/permits/?manager={self.manager.pk}")
        self.assertEqual(response.data["count"], 2)

        response = self.client.post("/api/compliance-milestones/", self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["current_status"], S.NOT_STARTED)
        self.assertEqual(response.data["manager_name"], self.manager.name)
        self.assertFalse(response.data["is_overdue"])

    def test_model_rules_apply(self, _today):
        response = self.client.post("/api/permits/", {
            "compliance_unit": str(self.unit.pk), "name": "Bad dates", "issuing_agency": "State DEQ",
            "manager": str(self.manager.pk), "effective_date": "2024-01-01", "expiration_date": "2023-12-31",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("expiration_date", response.data)
        response = self.client.post("/api/permits/", {
            "compliance_unit": str(self.unit.pk), "name": "External manager", "issuing_agency": "State DEQ",
            "manager": str(make_contact(contact_type="EXTERNAL").pk),
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("manager", response.data)

        for bad, field in [
            ({"target_date": "2026-08-01"}, "target_date"),
            ({"status": S.COMPLETE}, "submitted_date"),
            ({"manager": str(make_contact(contact_type="EXTERNAL").pk)}, "manager"),
            ({"status": "OVERDUE"}, "status"),  # derived, not a choice
        ]:
            response = self.client.post("/api/compliance-milestones/", self.payload(**bad), format="json")
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn(field, response.data)

    def test_status_filter_matches_displayed_status(self, _today):
        overdue = make_milestone(self.permit, name="Late", due_date=datetime.date(2026, 7, 1), status=S.IN_PROGRESS)
        upcoming = make_milestone(self.permit, name="Upcoming", due_date=datetime.date(2026, 7, 28), status=S.IN_PROGRESS)
        done = make_milestone(self.permit, name="Done", due_date=datetime.date(2026, 6, 28), status=S.COMPLETE,
                              submitted_date=datetime.date(2026, 6, 20))

        def names(query):
            response = self.client.get(f"/api/compliance-milestones/?{query}")
            self.assertEqual(response.status_code, 200)
            return sorted(r["name"] for r in response.data["results"])

        self.assertEqual(names("status=OVERDUE"), [overdue.name])
        self.assertEqual(names("status=IN_PROGRESS"), [upcoming.name])
        self.assertEqual(names("status=OPEN"), sorted([overdue.name, upcoming.name]))
        self.assertEqual(names("status=COMPLETE"), [done.name])
        self.assertEqual(names(f"compliance_unit={self.unit.pk}&due_date_after=2026-07-01"),
                         sorted([overdue.name, upcoming.name]))
        self.assertEqual(names(f"manager={self.manager.pk}&search=upcom"), [upcoming.name])
