"""
Project budgets, versioned by annual budget cycle.

Each year a project's budget is updated: a :class:`Budget` belongs to a project
and to the budget cycle it was prepared for (``budget_year``, e.g. the FY2027
budget). Versions move Draft → Submitted → Approved; approving one supersedes
the project's previously approved budget, so a project has at most one approved
budget at a time. A budget holds :class:`BudgetLineItem` rows (Design,
Construction, ...) and each line item holds one :class:`BudgetAmount` per
fiscal year.

The utility's fiscal year runs October 1 – September 30 and is named for the
calendar year it ends in: FY2027 is Oct 1, 2026 – Sep 30, 2027.

Relationships::

    Project ──< Budget ──< BudgetLineItem ──< BudgetAmount
                  └── superseded_by ──> Budget
"""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from pm.models import BaseModel, Project

FISCAL_YEAR_START_MONTH = 10
fiscal_year_validators = [MinValueValidator(2000), MaxValueValidator(2100)]


def fiscal_year(d):
    """The fiscal year containing date ``d``: Oct 1, 2026 – Sep 30, 2027 is FY2027."""
    return d.year + 1 if d.month >= FISCAL_YEAR_START_MONTH else d.year


def fiscal_year_dates(fy):
    """First and last day of fiscal year ``fy``."""
    return datetime.date(fy - 1, FISCAL_YEAR_START_MONTH, 1), datetime.date(fy, FISCAL_YEAR_START_MONTH - 1, 30)


def current_fiscal_year(today=None):
    return fiscal_year(today or timezone.localdate())


def next_budget_year(today=None):
    """The budget cycle being prepared now: next fiscal year's budget."""
    return current_fiscal_year(today) + 1


class Budget(BaseModel):
    """One version of a project's budget, prepared for one budget cycle."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        SUPERSEDED = "SUPERSEDED", "Superseded"
        REJECTED = "REJECTED", "Rejected"

    # Line items and amounts can only change while a budget is being prepared.
    EDITABLE_STATUSES = (Status.DRAFT, Status.SUBMITTED)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="budgets")
    budget_year = models.PositiveSmallIntegerField(
        "budget cycle (FY)",
        default=next_budget_year,
        validators=fiscal_year_validators,
        help_text=(
            "Fiscal year this budget is prepared for, e.g. 2027 for the FY2027 budget (Oct 1, 2026 – Sep 30, 2027)."
        ),
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    prepared_by = models.CharField(max_length=200, blank=True)
    submitted_date = models.DateField(null=True, blank=True)
    approved_by = models.CharField(max_length=200, blank=True, help_text="Person or body, e.g. Board of Commissioners.")
    approved_date = models.DateField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="supersedes",
        null=True,
        blank=True,
        editable=False,
        help_text="The approved budget that replaced this one.",
    )
    notes = models.TextField(blank=True, help_text="Basis of estimate and what changed from the previous version.")

    url_name = "budget"

    class Meta:
        ordering = ["-budget_year", "-project__project_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "budget_year"],
                name="one_budget_per_project_cycle",
                violation_error_message="This project already has a budget for that budget cycle.",
            ),
            # Kept by save(), which supersedes the previous approved budget; see get_constraints().
            models.UniqueConstraint(
                fields=["project"], condition=models.Q(status="APPROVED"), name="one_approved_budget_per_project"
            ),
        ]

    def __str__(self):
        return f"FY{self.budget_year} budget — {self.project.project_id}"

    def get_absolute_url(self):
        return f"{reverse('budgets:project-budget', args=[self.project_id])}?version={self.pk}"

    @property
    def name(self):
        return f"FY{self.budget_year} Budget"

    @property
    def is_editable(self):
        return self.status in self.EDITABLE_STATUSES

    @property
    def total(self):
        if not hasattr(self, "_total"):
            self._total = BudgetAmount.objects.filter(line_item__budget=self).aggregate(t=Sum("amount"))[
                "t"
            ] or Decimal(0)
        return self._total

    @property
    def fiscal_years(self):
        """The span of fiscal years with costs, e.g. "FY2027–FY2029"."""
        years = BudgetAmount.objects.filter(line_item__budget=self).aggregate(
            lo=models.Min("fiscal_year"), hi=models.Max("fiscal_year")
        )
        if years["lo"] is None:
            return ""
        return f"FY{years['lo']}" if years["lo"] == years["hi"] else f"FY{years['lo']}–FY{years['hi']}"

    @property
    def project_type(self):
        return self.project.get_project_type_display()

    def get_constraints(self):
        # Approving a budget is allowed even though another is approved: save() supersedes the old one.
        return [
            (model, [c for c in constraints if c.name != "one_approved_budget_per_project"])
            for model, constraints in super().get_constraints()
        ]

    def clean(self):
        errors = {}
        if self.status == self.Status.APPROVED:
            if not self.approved_by:
                errors["approved_by"] = "Approved budgets need an approver."
            if not self.approved_date:
                errors["approved_date"] = "Approved budgets need an approval date."
            if self.project_id and self.budget_year:
                newer = (
                    Budget.objects.filter(
                        project_id=self.project_id, status=self.Status.APPROVED, budget_year__gt=self.budget_year
                    )
                    .exclude(pk=self.pk)
                    .first()
                )
                if newer:
                    errors["status"] = (
                        f"The FY{newer.budget_year} budget is already approved; an older cycle can't replace it."
                    )
        if self.status == self.Status.SUBMITTED and not self.submitted_date:
            self.submitted_date = timezone.localdate()
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.status == self.Status.APPROVED:
                # Supersede the previous approved version first so the one-approved index holds.
                Budget.objects.filter(project_id=self.project_id, status=self.Status.APPROVED).exclude(
                    pk=self.pk
                ).update(status=self.Status.SUPERSEDED, superseded_by=self.pk, updated_at=timezone.now())
            super().save(*args, **kwargs)

    def copy(self, budget_year, prepared_by=""):
        """A new draft for ``budget_year`` with this budget's line items and amounts."""
        with transaction.atomic():
            new = Budget.objects.create(
                project=self.project,
                budget_year=budget_year,
                prepared_by=prepared_by or self.prepared_by,
                notes=f"Started from the FY{self.budget_year} budget ({self.get_status_display().lower()}).",
            )
            for item in self.line_items.prefetch_related("amounts"):
                copy = BudgetLineItem.objects.create(budget=new, category=item.category, description=item.description)
                BudgetAmount.objects.bulk_create(
                    [
                        BudgetAmount(line_item=copy, fiscal_year=a.fiscal_year, amount=a.amount)
                        for a in item.amounts.all()
                    ]
                )
        return new


def check_editable(budget):
    if budget is not None and not budget.is_editable:
        raise ValidationError(
            f"This budget is {budget.get_status_display().lower()}, so its line items can't change. "
            "Start a new version to update it."
        )


class BudgetLineItem(BaseModel):
    """A cost line in a budget, e.g. Construction — general contract."""

    class Category(models.TextChoices):
        DESIGN = "DESIGN", "Design"
        CONSTRUCTION = "CONSTRUCTION", "Construction"
        LAND = "LAND", "Land / Easement Acquisition"
        CAPITALIZED_OPERATING = "CAPITALIZED_OPERATING", "Operating Costs to be Capitalized"

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="line_items")
    category = models.CharField(max_length=30, choices=Category.choices)
    description = models.CharField(
        max_length=200, blank=True, help_text="Optional detail, e.g. 'Owner-furnished equipment'."
    )

    url_name = "budgetlineitem"

    class Meta:
        ordering = ["budget", "created_at"]
        verbose_name = "budget line item"

    def __str__(self):
        label = self.get_category_display()
        return f"{label} — {self.description}" if self.description else label

    def get_absolute_url(self):
        return self.budget.get_absolute_url()

    @property
    def total(self):
        return sum((a.amount for a in self.amounts.all()), Decimal(0))

    @property
    def sort_key(self):
        """Category order (Design first), then description."""
        return self.Category.values.index(self.category), self.description.lower()

    def clean(self):
        check_editable(self.budget if self.budget_id else None)


class BudgetAmount(BaseModel):
    """A line item's cost in one fiscal year."""

    line_item = models.ForeignKey(BudgetLineItem, on_delete=models.CASCADE, related_name="amounts")
    fiscal_year = models.PositiveSmallIntegerField(validators=fiscal_year_validators, help_text="e.g. 2027 for FY2027.")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["line_item", "fiscal_year"]
        verbose_name = "budget amount"
        constraints = [
            models.UniqueConstraint(
                fields=["line_item", "fiscal_year"],
                name="one_amount_per_line_item_year",
                violation_error_message="This line item already has an amount for that fiscal year.",
            )
        ]

    def __str__(self):
        return f"FY{self.fiscal_year}: {self.amount}"

    def get_absolute_url(self):
        return self.line_item.get_absolute_url()

    def clean(self):
        check_editable(self.line_item.budget if self.line_item_id else None)
