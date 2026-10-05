"""
Project planning models.

A project's plan is a :class:`ProjectPlan` (the narrative: problem statement
and scope, with an approval status) plus structured, trackable sections that
hang off the project: objectives, risks, stakeholders, milestones and
communication-plan items. :class:`ActivityNote` records progress narrative,
such as the project manager's monthly update.

Sections reference ``pm.Project`` directly (not the plan) so they can be
filtered across the portfolio, e.g. "all open high risks".
"""
import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from pm.models import BaseModel, Project


class ProjectPlan(BaseModel):
    """The narrative part of a project plan. One per project."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_REVIEW = "IN_REVIEW", "In Review"
        APPROVED = "APPROVED", "Approved"

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="plan")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    problem_statement = models.TextField(blank=True, help_text="What problem or need does this project address, and why now?")
    scope_in = models.TextField("in scope", blank=True, help_text="Work, deliverables and areas included in the project.")
    scope_out = models.TextField("out of scope", blank=True, help_text="Explicit exclusions, to prevent scope creep.")
    approved_by = models.CharField(max_length=200, blank=True)
    approved_date = models.DateField(null=True, blank=True)

    url_name = "plan"

    class Meta:
        ordering = ["-project__project_id"]
        verbose_name = "project plan"

    def __str__(self):
        return f"Plan — {self.project.project_id} {self.project.name}"

    def get_absolute_url(self):
        return reverse("planning:project-plan", args=[self.project_id])

    def clean(self):
        if self.status == self.Status.APPROVED and not (self.approved_by and self.approved_date):
            raise ValidationError("Approved plans need an approver and an approval date.")


class Objective(BaseModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        ON_TRACK = "ON_TRACK", "On Track"
        AT_RISK = "AT_RISK", "At Risk"
        ACHIEVED = "ACHIEVED", "Achieved"
        NOT_ACHIEVED = "NOT_ACHIEVED", "Not Achieved"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="objectives")
    description = models.CharField(max_length=300)
    success_measure = models.CharField(max_length=300, blank=True, help_text="How will we know it was achieved?")
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    order = models.PositiveSmallIntegerField(default=0, help_text="Display order (lowest first).")

    url_name = "objective"

    class Meta:
        ordering = ["project", "order", "created_at"]

    def __str__(self):
        return self.description


class Risk(BaseModel):
    """A risk register entry, scored likelihood × impact (1–25)."""

    class Category(models.TextChoices):
        TECHNICAL = "TECHNICAL", "Technical / Design"
        SCHEDULE = "SCHEDULE", "Schedule"
        COST = "COST", "Cost / Funding"
        REGULATORY = "REGULATORY", "Regulatory / Permitting"
        ENVIRONMENTAL = "ENVIRONMENTAL", "Environmental"
        SAFETY = "SAFETY", "Safety"
        STAKEHOLDER = "STAKEHOLDER", "Stakeholder / Community"
        OPERATIONS = "OPERATIONS", "Operations"
        PROCUREMENT = "PROCUREMENT", "Procurement / Supply Chain"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        MITIGATING = "MITIGATING", "Mitigating"
        CLOSED = "CLOSED", "Closed"

    LIKELIHOOD = [(1, "1 — Rare"), (2, "2 — Unlikely"), (3, "3 — Possible"), (4, "4 — Likely"), (5, "5 — Almost certain")]
    IMPACT = [(1, "1 — Negligible"), (2, "2 — Minor"), (3, "3 — Moderate"), (4, "4 — Major"), (5, "5 — Severe")]
    score_validators = [MinValueValidator(1), MaxValueValidator(5)]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="risks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    likelihood = models.PositiveSmallIntegerField(choices=LIKELIHOOD, validators=score_validators)
    impact = models.PositiveSmallIntegerField(choices=IMPACT, validators=score_validators)
    score = models.PositiveSmallIntegerField(editable=False, default=1, help_text="Likelihood × impact.")
    owner = models.CharField(max_length=200, blank=True, help_text="Person responsible for managing the risk.")
    mitigation = models.TextField("mitigation / response", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    identified_date = models.DateField(default=timezone.localdate)
    review_date = models.DateField("next review", null=True, blank=True)

    url_name = "risk"

    class Meta:
        ordering = ["-score", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.score = (self.likelihood or 1) * (self.impact or 1)
        super().save(*args, **kwargs)


class Stakeholder(BaseModel):
    class Level(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stakeholders")
    name = models.CharField(max_length=200, help_text="Person or group.")
    organization = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=200, blank=True, help_text="Role on or interest in the project.")
    influence = models.CharField(max_length=10, choices=Level.choices, default=Level.MEDIUM)
    interest = models.CharField(max_length=10, choices=Level.choices, default=Level.MEDIUM)
    contact = models.CharField(max_length=200, blank=True)
    engagement_notes = models.TextField(blank=True)

    url_name = "stakeholder"

    class Meta:
        ordering = ["project", "name"]

    def __str__(self):
        return f"{self.name} ({self.organization})" if self.organization else self.name

    @property
    def engagement_strategy(self):
        """Classic influence/interest grid quadrant."""
        high_influence = self.influence == self.Level.HIGH
        high_interest = self.interest == self.Level.HIGH
        if high_influence and high_interest:
            return "Manage closely"
        if high_influence:
            return "Keep satisfied"
        if high_interest:
            return "Keep informed"
        return "Monitor"


class Milestone(BaseModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        AT_RISK = "AT_RISK", "At Risk"
        COMPLETE = "COMPLETE", "Complete"
        MISSED = "MISSED", "Missed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=200)
    planned_date = models.DateField(help_text="Baseline date from the approved plan.")
    forecast_date = models.DateField(null=True, blank=True, help_text="Current expected date.")
    actual_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)

    url_name = "milestone"

    class Meta:
        ordering = ["project", "planned_date"]

    def __str__(self):
        return self.name

    @property
    def variance_days(self):
        """Days late (+) or early (−) versus the planned date, using actual, else forecast."""
        current = self.actual_date or self.forecast_date
        return (current - self.planned_date).days if current else None

    def clean(self):
        if self.status == self.Status.COMPLETE and not self.actual_date:
            raise ValidationError({"actual_date": "Completed milestones need an actual date."})


class CommunicationItem(BaseModel):
    """One row of the communication plan: who hears what, how and how often."""

    class Method(models.TextChoices):
        MEETING = "MEETING", "Meeting"
        EMAIL = "EMAIL", "Email"
        REPORT = "REPORT", "Written report"
        PRESENTATION = "PRESENTATION", "Presentation"
        PUBLIC_NOTICE = "PUBLIC_NOTICE", "Public notice / door hanger"
        WEBSITE = "WEBSITE", "Website / social media"
        NEWSLETTER = "NEWSLETTER", "Newsletter"

    class Frequency(models.TextChoices):
        WEEKLY = "WEEKLY", "Weekly"
        BIWEEKLY = "BIWEEKLY", "Every two weeks"
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"
        MILESTONE = "MILESTONE", "At milestones"
        AS_NEEDED = "AS_NEEDED", "As needed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="communication_items")
    purpose = models.CharField(max_length=200, help_text="What is communicated, e.g. 'Construction progress'.")
    audience = models.CharField(max_length=200)
    method = models.CharField(max_length=20, choices=Method.choices)
    frequency = models.CharField(max_length=20, choices=Frequency.choices)
    owner = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    url_name = "communicationitem"

    class Meta:
        ordering = ["project", "purpose"]
        verbose_name = "communication plan item"

    def __str__(self):
        return f"{self.purpose} → {self.audience}"


def first_of_month(d):
    return d.replace(day=1)


def previous_month(today=None):
    """First day of the month before ``today``."""
    today = today or timezone.localdate()
    return first_of_month(first_of_month(today) - datetime.timedelta(days=1))


class ActivityNote(BaseModel):
    """A dated note about project activity — most often the PM's monthly update."""

    class NoteType(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly update"
        DECISION = "DECISION", "Decision"
        ISSUE = "ISSUE", "Issue"
        GENERAL = "GENERAL", "General note"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activity_notes")
    note_type = models.CharField(max_length=20, choices=NoteType.choices, default=NoteType.MONTHLY)
    period = models.DateField(
        "reporting month", null=True, blank=True,
        help_text="For monthly updates: the month being reported on (stored as the 1st of the month).",
    )
    note_date = models.DateField(default=timezone.localdate)
    author_name = models.CharField("author", max_length=200)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField()

    url_name = "activitynote"

    class Meta:
        ordering = ["-note_date", "-created_at"]
        verbose_name = "activity note"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "period"],
                condition=models.Q(note_type="MONTHLY"),
                name="one_monthly_update_per_project_month",
                violation_error_message="This project already has a monthly update for that month.",
            ),
        ]

    def __str__(self):
        if self.note_type == self.NoteType.MONTHLY and self.period:
            return f"{self.period:%B %Y} update — {self.project.project_id}"
        return self.title or f"{self.get_note_type_display()} — {self.note_date:%b} {self.note_date.day}, {self.note_date.year}"

    def clean(self):
        if self.period:
            self.period = first_of_month(self.period)
        if self.note_type == self.NoteType.MONTHLY and not self.period:
            raise ValidationError({"period": "Monthly updates need a reporting month."})
