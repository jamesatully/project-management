"""
Permit compliance models.

A compliance unit (``pm.ComplianceUnit``) holds one or more :class:`Permit`
records, and each permit has :class:`ComplianceMilestone` records: the reports,
submittals and other deliverables its conditions require, e.g. a drinking water
system's monthly operating report. A recurring requirement is entered as one
milestone per occurrence, so each has its own due date, status and submittal.

"Overdue" isn't stored: a milestone is overdue when its due date has passed and
it hasn't been submitted or completed (see :attr:`ComplianceMilestone.current_status`).
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, F, Q, Value, When
from django.utils import timezone

from pm.models import BaseModel, ComplianceUnit, Contact, Document


def check_internal(contact, field, errors, label):
    """Managers must be utility staff. limit_choices_to covers forms; this covers the API and later edits."""
    if contact and contact.contact_type != Contact.ContactType.INTERNAL:
        errors[field] = f"The {label} must be an internal contact."


class Permit(BaseModel):
    """A permit, registration or approval issued to the utility for a compliance unit."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Application Pending"
        ACTIVE = "ACTIVE", "Active"
        EXTENDED = "EXTENDED", "Administratively Extended"
        EXPIRED = "EXPIRED", "Expired"
        TERMINATED = "TERMINATED", "Terminated"

    compliance_unit = models.ForeignKey(ComplianceUnit, on_delete=models.PROTECT, related_name="permits")
    name = models.CharField("permit name", max_length=200)
    permit_number = models.CharField(
        "permit number", max_length=50, blank=True, help_text="Number assigned by the issuing agency."
    )
    issuing_agency = models.CharField(max_length=200)
    manager = models.ForeignKey(
        Contact,
        verbose_name="permit manager",
        on_delete=models.PROTECT,
        related_name="managed_permits",
        limit_choices_to={"contact_type": Contact.ContactType.INTERNAL},
        help_text="Utility staff member responsible for the permit overall (an internal contact).",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, help_text="What the permit covers and any notes on its conditions.")

    url_name = "permit"

    class Meta:
        ordering = ["compliance_unit__name", "name"]

    def __str__(self):
        return self.name

    @property
    def next_due(self):
        """Due date of the earliest milestone not yet submitted or completed."""
        milestone = self.milestones.open().order_by("due_date").first()
        return milestone.due_date if milestone else None

    def clean(self):
        errors = {}
        check_internal(self.manager if self.manager_id else None, "manager", errors, "permit manager")
        if self.effective_date and self.expiration_date and self.expiration_date < self.effective_date:
            errors["expiration_date"] = "Expiration date cannot be before the effective date."
        if errors:
            raise ValidationError(errors)


class ComplianceMilestoneQuerySet(models.QuerySet):
    def open(self):
        """Not yet submitted or completed (including overdue)."""
        return self.exclude(status__in=ComplianceMilestone.MET_STATUSES)

    def overdue(self, today=None):
        return self.open().filter(due_date__lt=today or timezone.localdate())


# Statuses that meet a milestone; anything else is open.
MET = ["SUBMITTED", "COMPLETE"]


class ComplianceMilestone(BaseModel):
    """
    A permit-required deliverable or action with a regulatory due date.

    Default order: open milestones first, soonest due at the top (so overdue ones lead),
    then submitted and complete ones, most recent first.
    """

    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SUBMITTED = "SUBMITTED", "Submitted"
        COMPLETE = "COMPLETE", "Complete"

    # Derived status shown for open milestones past their due date; never stored.
    OVERDUE = "OVERDUE"
    MET_STATUSES = MET

    permit = models.ForeignKey(Permit, on_delete=models.CASCADE, related_name="milestones")
    manager = models.ForeignKey(
        Contact,
        verbose_name="milestone manager",
        on_delete=models.PROTECT,
        related_name="compliance_milestones",
        limit_choices_to={"contact_type": Contact.ContactType.INTERNAL},
        help_text="Utility staff member who coordinates, tracks and confirms completion (an internal contact).",
    )
    name = models.CharField(
        "milestone name", max_length=200, help_text="Short title of the required deliverable or action."
    )
    permit_condition = models.CharField(
        "permit condition #", max_length=50, help_text="Permit condition that requires this milestone, e.g. S1.B."
    )
    due_date = models.DateField(help_text="Regulatory deadline to complete or submit this milestone.")
    target_date = models.DateField(
        "internal target date", null=True, blank=True,
        help_text="Internal completion date ahead of the due date, to allow for review before submittal.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    submitted_date = models.DateField(
        "date submitted / completed", null=True, blank=True,
        help_text="Required once the milestone is submitted or complete.",
    )
    submittal_document = models.ForeignKey(
        Document,
        verbose_name="milestone submittal document",
        on_delete=models.PROTECT,
        related_name="compliance_milestones",
        null=True,
        blank=True,
        help_text="The submittal or record, filed under this permit's compliance unit.",
    )
    description = models.TextField(blank=True, help_text="The requirement, the expected action and related obligations.")

    objects = ComplianceMilestoneQuerySet.as_manager()

    url_name = "compliancemilestone"

    class Meta:
        ordering = [
            Case(When(status__in=MET, then=Value(1)), default=Value(0)).asc(),
            Case(When(~Q(status__in=MET), then=F("due_date"))).asc(nulls_last=True),
            F("due_date").desc(),
            "name",
        ]
        verbose_name = "compliance milestone"

    def __str__(self):
        return self.name

    @property
    def is_overdue(self):
        return self.status not in self.MET_STATUSES and self.due_date < timezone.localdate()

    @property
    def current_status(self):
        """The stored status, or ``OVERDUE`` when past due and not yet submitted or complete."""
        return self.OVERDUE if self.is_overdue else self.status

    def get_current_status_display(self):
        return "Overdue" if self.is_overdue else self.get_status_display()

    @property
    def variance_days(self):
        """Days the submittal was late (+) or early (−) versus the due date."""
        return (self.submitted_date - self.due_date).days if self.submitted_date else None

    def clean(self):
        errors = {}
        check_internal(self.manager if self.manager_id else None, "manager", errors, "milestone manager")
        if self.target_date and self.due_date and self.target_date > self.due_date:
            errors["target_date"] = "The internal target date should be on or before the due date."
        if self.status in self.MET_STATUSES and not self.submitted_date:
            errors["submitted_date"] = "Submitted and complete milestones need the date submitted / completed."
        if self.submitted_date and self.submitted_date > timezone.localdate():
            errors["submitted_date"] = "The date submitted / completed can't be in the future."
        document = self.submittal_document if self.submittal_document_id else None
        if document and self.permit_id and document.compliance_unit_id != self.permit.compliance_unit_id:
            errors["submittal_document"] = (
                f"Choose a document linked to this permit's compliance unit ({self.permit.compliance_unit})."
            )
        if errors:
            raise ValidationError(errors)
