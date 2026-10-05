"""
Domain models for the project management app.

Relationships::

    Vendor ──< PurchaseOrder ──< Invoice
                    │
    Project ──< (optional) PurchaseOrder
       └──< FieldReport

    Document ──> Project, ComplianceUnit, PurchaseOrder, Invoice
                 (each optional; at least one required)

Every model uses a UUID primary key and carries ``created_at`` / ``updated_at``
audit timestamps via :class:`BaseModel`.
"""
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

project_id_validator = RegexValidator(
    regex=r"^\d{4}-\d+-\d+-\d+$",
    message="Project ID must look like 2021-2-20-0 (year-#-#-#).",
)
budget_id_validator = RegexValidator(
    regex=r"^\d+$",
    message="Budget ID must contain digits only (e.g. 6822015).",
)


class BaseModel(models.Model):
    """Abstract base: UUID primary key plus audit timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Name of the URL namespace entry used by get_absolute_url; set on subclasses.
    url_name = None

    class Meta:
        abstract = True

    def get_absolute_url(self):
        return reverse(f"pm:{self.url_name}-detail", args=[self.pk])


class Vendor(BaseModel):
    """A company that supplies goods or services under purchase orders."""

    name = models.CharField(max_length=200, unique=True)
    mailing_address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    primary_contact_name = models.CharField(max_length=200, blank=True)
    primary_contact_phone = models.CharField("primary contact phone number", max_length=40, blank=True)

    url_name = "vendor"

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ComplianceUnit(BaseModel):
    """
    A regulated system or permit the utility reports on, e.g. the "Northwest
    Wastewater Treatment System" or a water use permit.
    """

    class UnitType(models.TextChoices):
        WATER_USE_PERMIT = "WATER_USE_PERMIT", "Water Use Permit"
        PUBLIC_WATER_SUPPLY = "PUBLIC_WATER_SUPPLY", "Public Water Supply"
        WASTEWATER = "WASTEWATER", "Wastewater"
        TANK = "TANK", "Tank"
        STORMWATER = "STORMWATER", "Stormwater"
        OTHER = "OTHER", "Other"

    name = models.CharField("unit name", max_length=200, unique=True)
    unit_type = models.CharField(max_length=30, choices=UnitType.choices)

    url_name = "complianceunit"

    class Meta:
        ordering = ["name"]
        verbose_name = "compliance unit"

    def __str__(self):
        return self.name


class Project(BaseModel):
    """A capital, development or environmental project."""

    class ProjectType(models.TextChoices):
        CIP_EXPANSION = "CIP_EXPANSION", "CIP Expansion"
        CIP_RR = "CIP_RR", "CIP R&R"  # renewal and replacement
        DEVELOPMENT = "DEVELOPMENT", "Development"

    class Status(models.TextChoices):
        PLANNING = "PLANNING", "Planning"
        DESIGN = "DESIGN", "Design"
        CONSTRUCTION = "CONSTRUCTION", "Construction"
        ON_HOLD = "ON_HOLD", "On Hold"
        COMPLETE = "COMPLETE", "Complete"
        CANCELLED = "CANCELLED", "Cancelled"

    name = models.CharField(max_length=200)
    project_id = models.CharField(
        "project ID",
        max_length=30,
        unique=True,
        validators=[project_id_validator],
        help_text="Manually assigned identifier, e.g. 2021-2-20-0. Must be unique.",
    )
    budget_id = models.CharField(
        "budget ID",
        max_length=20,
        validators=[budget_id_validator],
        db_index=True,
        help_text="Budget/fund number, e.g. 6822015. May be shared by several projects.",
    )
    project_type = models.CharField(max_length=20, choices=ProjectType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    project_manager = models.CharField(max_length=200, help_text="Project manager's name.")

    url_name = "project"

    class Meta:
        ordering = ["-project_id"]

    def __str__(self):
        return f"{self.project_id} — {self.name}"


class PurchaseOrder(BaseModel):
    """A purchase order issued to a vendor, optionally tied to a project."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    po_number = models.CharField("purchase order number", max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        null=True,
        blank=True,
        help_text="Project this PO is charged to (optional).",
    )
    contract_number = models.CharField(max_length=50, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    url_name = "purchaseorder"

    class Meta:
        ordering = ["-po_number"]
        verbose_name = "purchase order"

    def __str__(self):
        return f"PO {self.po_number}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})


class Invoice(BaseModel):
    """A vendor invoice billed against a purchase order."""

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"

    invoice_number = models.CharField(max_length=50, help_text="Vendor's invoice number.")
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="invoices")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    invoice_date = models.DateField()
    received_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)

    url_name = "invoice"

    class Meta:
        ordering = ["-invoice_date"]
        constraints = [
            # Invoice numbers are vendor-defined, so they only need to be unique per vendor.
            models.UniqueConstraint(fields=["vendor", "invoice_number"], name="unique_invoice_per_vendor"),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number}"

    def clean(self):
        errors = {}
        if self.purchase_order_id and self.vendor_id and self.purchase_order.vendor_id != self.vendor_id:
            errors["purchase_order"] = "Purchase order belongs to a different vendor."
        if self.status == self.Status.PAID and not self.paid_date:
            errors["paid_date"] = "Paid invoices need a paid date."
        if errors:
            raise ValidationError(errors)


class FieldReport(BaseModel):
    """A daily site visit report for a project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="field_reports")
    entered_by = models.CharField(max_length=200, help_text="Name of the person who wrote the report.")
    report_date = models.DateField("field report date")
    data_entry_date = models.DateField(default=timezone.localdate)
    time_on_site = models.DecimalField(
        "time on site (hours)", max_digits=5, decimal_places=2, validators=[MinValueValidator(0)]
    )
    observation_notes = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    weather_notes = models.TextField(blank=True)

    url_name = "fieldreport"

    class Meta:
        ordering = ["-report_date"]
        verbose_name = "field report"

    def __str__(self):
        return f"Field report {self.report_date} — {self.project.project_id}"


class Document(BaseModel):
    """
    Correspondence or a record (letter, RFI, submittal, report, ...).

    A document links to any combination of a project, compliance unit,
    purchase order and invoice, but must link to at least one. Links use
    PROTECT: a record can't be deleted while documents still reference it.
    """

    class DocumentType(models.TextChoices):
        LETTER = "LETTER", "Letter"
        MEMO = "MEMO", "Memo"
        EMAIL = "EMAIL", "Email"
        RFI = "RFI", "RFI"
        SUBMITTAL = "SUBMITTAL", "Submittal"
        CHANGE_ORDER = "CHANGE_ORDER", "Change Order"
        MEETING_MINUTES = "MEETING_MINUTES", "Meeting Minutes"
        REPORT = "REPORT", "Report"
        DRAWING = "DRAWING", "Drawing"
        OTHER = "OTHER", "Other"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="documents", null=True, blank=True)
    compliance_unit = models.ForeignKey(
        ComplianceUnit, on_delete=models.PROTECT, related_name="documents", null=True, blank=True
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="documents", null=True, blank=True
    )
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="documents", null=True, blank=True)
    subject = models.CharField(max_length=300)
    originating_organization = models.CharField(max_length=200)
    recipient_organization = models.CharField(max_length=200)
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    document_date = models.DateField()
    added_date = models.DateTimeField(auto_now_add=True)
    last_edited_date = models.DateTimeField(auto_now=True)

    url_name = "document"
    LINK_FIELDS = ["project", "compliance_unit", "purchase_order", "invoice"]

    class Meta:
        ordering = ["-document_date"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(project__isnull=False)
                    | models.Q(compliance_unit__isnull=False)
                    | models.Q(purchase_order__isnull=False)
                    | models.Q(invoice__isnull=False)
                ),
                name="document_has_link",
                violation_error_message=(
                    "Link the document to at least one project, compliance unit, purchase order or invoice."
                ),
            ),
        ]

    def __str__(self):
        return self.subject

    @property
    def linked_records(self):
        """The records this document is linked to, in a fixed order."""
        return [obj for obj in (getattr(self, f) for f in self.LINK_FIELDS) if obj is not None]
