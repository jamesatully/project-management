"""Minimal object builders for compliance tests."""
import datetime

from pm.models import Contact
from pm.tests.factories import make_compliance_unit

from ..models import ComplianceMilestone, Permit


def make_permit(unit=None, **kw):
    defaults = {"name": "Riverbend WWTP NPDES Permit", "permit_number": "RB-0021457", "issuing_agency": "State DEQ"}
    return Permit.objects.create(compliance_unit=unit or make_compliance_unit(), **{**defaults, **kw})


def make_compliance_manager(name="Casey Example"):
    contact, _ = Contact.objects.get_or_create(
        name=name, contact_type=Contact.ContactType.INTERNAL,
        defaults={"title": "Compliance Specialist", "organization": "Regulatory Compliance"},
    )
    return contact


def make_milestone(permit, **kw):
    defaults = {
        "name": "Discharge Monitoring Report — May 2026",
        "permit_condition": "S1.A",
        "due_date": datetime.date(2026, 6, 28),
    }
    if "manager" not in kw:
        kw["manager"] = make_compliance_manager()
    return ComplianceMilestone.objects.create(permit=permit, **{**defaults, **kw})
