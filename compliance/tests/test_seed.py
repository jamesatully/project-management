import datetime
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from pm.models import ComplianceUnit

from ..models import ComplianceMilestone, Permit

TODAY = datetime.date(2026, 6, 30)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class ComplianceSeedTests(TestCase):
    def seed(self, *args):
        call_command("seed_demo", "--projects", "15", "--today", TODAY.isoformat(), *args, stdout=StringIO())

    def test_seed_demo_includes_permits_and_milestones(self, _today):
        self.seed()
        units_with_permits = set(Permit.objects.values_list("compliance_unit", flat=True))
        self.assertEqual(units_with_permits, set(ComplianceUnit.objects.values_list("pk", flat=True)))
        for permit in Permit.objects.select_related("manager"):
            self.assertEqual(permit.manager.contact_type, "INTERNAL")
        milestones = ComplianceMilestone.objects.select_related("permit", "manager", "submittal_document")
        self.assertGreater(milestones.count(), 200)
        self.assertTrue(milestones.overdue().exists())
        self.assertTrue(milestones.open().filter(due_date__gte=TODAY).exists())
        self.assertTrue(milestones.filter(submittal_document__isnull=False).exists())
        for m in milestones:
            m.full_clean()
            self.assertEqual(m.manager.contact_type, "INTERNAL")
            if m.submittal_document:
                self.assertEqual(m.submittal_document.compliance_unit_id, m.permit.compliance_unit_id)
                self.assertLessEqual(m.submitted_date, m.due_date)

    def test_flush_removes_milestones_that_protect_pm_records(self, _today):
        self.seed()
        first = sorted(ComplianceMilestone.objects.values_list("name", "due_date", "status"))
        self.seed("--flush")
        self.assertEqual(first, sorted(ComplianceMilestone.objects.values_list("name", "due_date", "status")))
