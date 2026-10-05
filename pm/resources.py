"""
Resource registry for the web UI.

Each :class:`Resource` describes how one model is presented: which columns the
list table shows, which fields are searchable, which FilterSet drives the
filter bar, and which related tables appear on the detail page. The generic
views in :mod:`pm.views` and the shared templates render entirely from this
configuration, so adding a model to the UI is mostly a matter of adding an
entry here.

Other apps extend the UI without ``pm`` importing them: call :func:`register`,
:func:`register_tab` and :func:`register_dashboard_panel` from their
``AppConfig.ready()`` (see ``planning/apps.py``).

Column ``kind`` values (rendered by ``pm.templatetags.pm_tags.cell``):
``link`` (links to the detail page), ``text``, ``money``, ``date``,
``status`` (coloured badge), ``fk`` (links to the related object's page),
``hours``, ``score`` (1-25 risk score badge), ``month`` (e.g. "Sep 2026"),
``days`` (signed day variance). A column may name a model property instead of
a field; such columns are not sortable.
"""
from dataclasses import dataclass, field

from . import filters, forms
from .models import Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor


@dataclass(frozen=True)
class Column:
    name: str
    label: str
    kind: str = "text"


@dataclass(frozen=True)
class Related:
    """A table of related objects shown on a detail page."""

    accessor: str  # reverse relation name on the parent, e.g. "purchase_orders"
    resource: str  # key of the child resource in REGISTRY
    fk_name: str  # name of the FK on the child pointing back at the parent


@dataclass(frozen=True)
class Tab:
    """An extra tab on a resource's detail page, e.g. "Plan" on projects."""

    label: str
    url_name: str  # reversed with the object's pk


@dataclass(frozen=True)
class Resource:
    key: str  # URL slug and url-name prefix
    model: type
    form_class: type
    filterset_class: type
    icon: str  # name of an inline SVG icon in templates/partials/icon.html
    columns: list = field(default_factory=list)
    search_fields: list = field(default_factory=list)
    select_related: list = field(default_factory=list)
    related: list = field(default_factory=list)
    # Fields shown on the detail page; defaults to every concrete field.
    detail_fields: list = field(default_factory=list)
    url_prefix: str = ""  # e.g. "projects" -> /projects/
    nav_group: str | None = "Records"  # sidebar heading; None hides it from the sidebar

    @property
    def verbose_name(self):
        return self.model._meta.verbose_name.title()

    @property
    def verbose_name_plural(self):
        return self.model._meta.verbose_name_plural.title()


REGISTRY = {
    r.key: r
    for r in [
        Resource(
            key="project",
            url_prefix="projects",
            model=Project,
            form_class=forms.ProjectForm,
            filterset_class=filters.ProjectFilter,
            icon="folder",
            columns=[
                Column("project_id", "Project ID", "link"),
                Column("name", "Name"),
                Column("budget_id", "Budget ID"),
                Column("project_type", "Type"),
                Column("status", "Status", "status"),
                Column("project_manager", "Project Manager"),
            ],
            search_fields=["name", "project_id", "budget_id", "project_manager"],
            related=[
                Related("purchase_orders", "purchaseorder", "project"),
                Related("field_reports", "fieldreport", "project"),
                Related("documents", "document", "project"),
            ],
        ),
        Resource(
            key="purchaseorder",
            url_prefix="purchase-orders",
            model=PurchaseOrder,
            form_class=forms.PurchaseOrderForm,
            filterset_class=filters.PurchaseOrderFilter,
            icon="cart",
            columns=[
                Column("po_number", "PO Number", "link"),
                Column("vendor", "Vendor", "fk"),
                Column("project", "Project", "fk"),
                Column("amount", "Amount", "money"),
                Column("status", "Status", "status"),
                Column("start_date", "Start", "date"),
                Column("end_date", "End", "date"),
            ],
            search_fields=["po_number", "contract_number", "vendor__name", "project__name", "project__project_id"],
            select_related=["vendor", "project"],
            related=[Related("invoices", "invoice", "purchase_order")],
        ),
        Resource(
            key="invoice",
            url_prefix="invoices",
            model=Invoice,
            form_class=forms.InvoiceForm,
            filterset_class=filters.InvoiceFilter,
            icon="receipt",
            columns=[
                Column("invoice_number", "Invoice #", "link"),
                Column("vendor", "Vendor", "fk"),
                Column("purchase_order", "PO", "fk"),
                Column("amount", "Amount", "money"),
                Column("status", "Status", "status"),
                Column("invoice_date", "Invoice Date", "date"),
                Column("paid_date", "Paid", "date"),
            ],
            search_fields=["invoice_number", "vendor__name", "purchase_order__po_number"],
            select_related=["vendor", "purchase_order"],
        ),
        Resource(
            key="fieldreport",
            url_prefix="field-reports",
            model=FieldReport,
            form_class=forms.FieldReportForm,
            filterset_class=filters.FieldReportFilter,
            icon="clipboard",
            columns=[
                Column("report_date", "Report Date", "link"),
                Column("project", "Project", "fk"),
                Column("entered_by", "Entered By"),
                Column("time_on_site", "Hours", "hours"),
                Column("data_entry_date", "Entered", "date"),
            ],
            search_fields=["entered_by", "observation_notes", "safety_notes", "weather_notes", "project__name"],
            select_related=["project"],
        ),
        Resource(
            key="document",
            url_prefix="documents",
            model=Document,
            form_class=forms.DocumentForm,
            filterset_class=filters.DocumentFilter,
            icon="document",
            columns=[
                Column("subject", "Subject", "link"),
                Column("project", "Project", "fk"),
                Column("document_type", "Type"),
                Column("originating_organization", "From"),
                Column("recipient_organization", "To"),
                Column("document_date", "Date", "date"),
            ],
            search_fields=["subject", "originating_organization", "recipient_organization", "project__name"],
            select_related=["project"],
        ),
        Resource(
            key="vendor",
            url_prefix="vendors",
            model=Vendor,
            form_class=forms.VendorForm,
            filterset_class=filters.VendorFilter,
            icon="building",
            columns=[
                Column("name", "Name", "link"),
                Column("primary_contact_name", "Primary Contact"),
                Column("primary_contact_phone", "Phone"),
                Column("website", "Website"),
            ],
            search_fields=["name", "primary_contact_name", "mailing_address"],
            related=[
                Related("purchase_orders", "purchaseorder", "vendor"),
                Related("invoices", "invoice", "vendor"),
            ],
        ),
    ]
}


# resource key -> extra detail-page tabs (the "Overview" tab is implicit).
DETAIL_TABS = {}

# Callables ``fn(request) -> dict | None``; a dict must include "template" and
# is passed to that template as ``panel``. Rendered at the end of the dashboard.
DASHBOARD_PANELS = []


def register(resource):
    """Add a resource (generic list/detail/create/edit/delete pages and API-style filtering)."""
    REGISTRY[resource.key] = resource


def register_tab(resource_key, tab):
    DETAIL_TABS.setdefault(resource_key, []).append(tab)


def register_dashboard_panel(fn):
    DASHBOARD_PANELS.append(fn)
