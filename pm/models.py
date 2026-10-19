"""
Domain models for the project management app.

Relationships::

    Vendor ──< PurchaseOrder ──< Invoice
                    │
    Project ──< (optional) PurchaseOrder
       └──< FieldReport

    Document ──> Project, ComplianceUnit, PurchaseOrder, Invoice
                 (each optional; at least one required) + optional file

    Contact ──> (optional) User


Every model uses a UUID primary key and carries ``created_at`` / ``updated_at``
audit timestamps via :class:`BaseModel`.
"""
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models.fields.files import FieldFile
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


class Contact(BaseModel):
    """
    A person (or group) the utility deals with, inside or outside the organization.

    Contacts are the shared address book: other apps reference them, e.g. planning
    stakeholders. A contact may be linked to an app user account, but most aren't.
    """

    class ContactType(models.TextChoices):
        INTERNAL = "INTERNAL", "Internal"
        EXTERNAL = "EXTERNAL", "External"

    name = models.CharField(max_length=200, help_text="Person's full name, or a group such as a board or committee.")
    title = models.CharField("job title", max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    contact_type = models.CharField(
        "internal / external", max_length=10, choices=ContactType.choices, default=ContactType.EXTERNAL,
        help_text="Internal: works for the utility. External: agencies, consultants, contractors, the public.",
    )
    role_description = models.TextField(
        "role in organization", blank=True, help_text="What they do and what they're responsible for."
    )
    email = models.EmailField(blank=True)
    phone = models.CharField("phone number", max_length=40, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="app user",
        on_delete=models.SET_NULL,
        related_name="contact",
        null=True,
        blank=True,
        help_text="App user account for this person, if they have one.",
    )

    url_name = "contact"

    class Meta:
        ordering = ["name", "organization"]

    def __str__(self):
        return f"{self.name} ({self.organization})" if self.organization else self.name


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
    project_manager = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="managed_projects",
        limit_choices_to={"contact_type": Contact.ContactType.INTERNAL},
        help_text="Utility staff member managing the project (an internal contact).",
    )

    url_name = "project"

    class Meta:
        ordering = ["-project_id"]

    def __str__(self):
        return f"{self.project_id} — {self.name}"

    def clean(self):
        # limit_choices_to covers forms; this covers the API and contacts later switched to External.
        manager = getattr(self, "project_manager", None) if self.project_manager_id else None
        if manager and manager.contact_type != Contact.ContactType.INTERNAL:
            raise ValidationError({"project_manager": "The project manager must be an internal contact."})


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


class ProtectedFieldFile(FieldFile):
    """An uploaded file whose ``url`` is the login-protected view that serves it, not a public media URL."""

    @property
    def url(self):
        self._require_file()
        return reverse(f"pm:{self.instance.url_name}-file", args=[self.instance.pk])

    @property
    def filename(self):
        return os.path.basename(self.name)

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lstrip(".").upper()


class ProtectedFileField(models.FileField):
    """FileField served only to logged-in users through ``pm:<url_name>-file`` (see ``views.DocumentFileView``)."""

    attr_class = ProtectedFieldFile


DOCUMENT_FILE_EXTENSIONS = [
    "pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "odt", "ods", "odp", "rtf", "txt",
    "msg", "eml", "png", "jpg", "jpeg", "tif", "tiff",
]
DOCUMENT_FILE_MAX_MB = 50


def validate_file_size(file):
    if file.size > DOCUMENT_FILE_MAX_MB * 1024 * 1024:
        raise ValidationError(f"Files can be at most {DOCUMENT_FILE_MAX_MB} MB.")


def document_upload_to(instance, filename):
    # One folder per document keeps the original file name (Django only sanitizes it).
    return f"documents/{instance.pk}/{filename}"


class Document(BaseModel):
    """
    Correspondence or a record (letter, RFI, submittal, report, ...).

    A document links to any combination of a project, compliance unit,
    purchase order and invoice, but must link to at least one. Links use
    PROTECT: a record can't be deleted while documents still reference it.

    It may carry one uploaded file (mostly PDFs), stored under MEDIA_ROOT and
    served only to logged-in users. Replaced or removed files are deleted from
    storage (see ``pm.signals``).
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
    file = ProtectedFileField(
        upload_to=document_upload_to,
        max_length=255,
        blank=True,
        validators=[FileExtensionValidator(DOCUMENT_FILE_EXTENSIONS), validate_file_size],
        help_text=f"PDF, Word, Excel, PowerPoint, text, email or image file, up to {DOCUMENT_FILE_MAX_MB} MB.",
    )
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
