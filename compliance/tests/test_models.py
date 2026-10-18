import datetime
from unittest import mock

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from pm.models import ComplianceUnit
from pm.tests.factories import make_compliance_unit, make_contact, make_document

from ..models import ComplianceMilestone, Permit
from .factories import make_compliance_manager, make_milestone, make_permit

S = ComplianceMilestone.Status
TODAY = datetime.date(2026, 7, 10)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class ComplianceModelTests(TestCase):
    def setUp(self):
        self.unit = make_compliance_unit()
        self.permit = make_permit(self.unit)

    def test_permit_expiration_cannot_precede_effective_date(self, _today):
        permit = Permit(compliance_unit=self.unit, name="NPDES", issuing_agency="DEQ",
                        effective_date=datetime.date(2026, 1, 1), expiration_date=datetime.date(2025, 12, 31))
        with self.assertRaises(ValidationError) as ctx:
            permit.full_clean()
        self.assertIn("expiration_date", ctx.exception.message_dict)

    def test_overdue_is_derived_from_due_date_and_status(self, _today):
        past = make_milestone(self.permit, due_date=datetime.date(2026, 7, 9), status=S.IN_PROGRESS)
        today = make_milestone(self.permit, due_date=TODAY)
        met = make_milestone(self.permit, due_date=datetime.date(2026, 6, 28), status=S.SUBMITTED,
                             submitted_date=datetime.date(2026, 6, 30))
        self.assertTrue(past.is_overdue)
        self.assertEqual((past.current_status, past.get_current_status_display()), ("OVERDUE", "Overdue"))
        self.assertFalse(today.is_overdue)  # due today is not yet overdue
        self.assertEqual(today.current_status, S.NOT_STARTED)
        self.assertEqual((met.current_status, met.variance_days), (S.SUBMITTED, 2))
        self.assertEqual(list(ComplianceMilestone.objects.overdue()), [past])
        self.assertCountEqual(ComplianceMilestone.objects.open(), [past, today])

    def test_target_date_must_not_be_after_due_date(self, _today):
        m = ComplianceMilestone(permit=self.permit, manager=self.manager(), name="DMR", permit_condition="S1.A",
                                due_date=datetime.date(2026, 7, 28), target_date=datetime.date(2026, 7, 29))
        self.assertInvalid(m, "target_date")
        m.target_date = datetime.date(2026, 7, 28)
        m.full_clean()

    def test_submitted_and_complete_need_a_submitted_date_not_in_the_future(self, _today):
        m = ComplianceMilestone(permit=self.permit, manager=self.manager(), name="DMR", permit_condition="S1.A",
                                due_date=datetime.date(2026, 7, 28), status=S.COMPLETE)
        self.assertInvalid(m, "submitted_date")
        m.submitted_date = datetime.date(2026, 7, 11)
        self.assertInvalid(m, "submitted_date")
        m.submitted_date = TODAY
        m.full_clean()

    def test_manager_must_be_internal(self, _today):
        m = ComplianceMilestone(permit=self.permit, manager=make_contact(contact_type="EXTERNAL"), name="DMR",
                                permit_condition="S1.A", due_date=TODAY)
        self.assertInvalid(m, "manager")

    def test_submittal_document_must_be_filed_under_the_permits_unit(self, _today):
        other_unit = make_compliance_unit(name="North Fork PWS", unit_type=ComplianceUnit.UnitType.PUBLIC_WATER_SUPPLY)
        m = ComplianceMilestone(permit=self.permit, manager=self.manager(), name="DMR", permit_condition="S1.A",
                                due_date=TODAY, submittal_document=make_document(compliance_unit=other_unit))
        self.assertInvalid(m, "submittal_document")
        m.submittal_document = make_document(compliance_unit=self.unit, subject="DMR — May 2026")
        m.full_clean()

    def test_delete_rules(self, _today):
        doc = make_document(compliance_unit=self.unit)
        make_milestone(self.permit, submittal_document=doc)
        with self.assertRaises(ProtectedError):
            doc.delete()
        with self.assertRaises(ProtectedError):
            self.unit.delete()  # the unit has a permit
        self.permit.delete()  # milestones go with their permit
        self.assertFalse(ComplianceMilestone.objects.exists())

    def manager(self):
        return make_compliance_manager()

    def assertInvalid(self, obj, field):
        with self.assertRaises(ValidationError) as ctx:
            obj.full_clean()
        self.assertIn(field, ctx.exception.message_dict)
