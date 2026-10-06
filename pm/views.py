"""
Web UI views.

The dashboard is a bespoke view; everything else is handled by five generic
CRUD views (list / detail / create / update / delete) driven by the resource
registry in :mod:`pm.resources`. ``pm/urls.py`` wires one set of URLs per
resource.
"""
from functools import reduce
from operator import or_

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views import generic

from . import display
from .forms import INPUT_CLASSES
from .models import Document, FieldReport, Invoice, Project, PurchaseOrder
from .resources import DASHBOARD_PANELS, DETAIL_TABS, REGISTRY, Tab

ZERO = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))


def safe_next(request):
    """The ``?next=`` URL if it points back into this site, else None."""
    url = request.GET.get("next")
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return None


def detail_tabs(resource_key, obj, active_url_name):
    """Tabs for a detail page: an implicit "Overview" plus any registered by other apps."""
    tabs = [Tab("Overview", f"pm:{resource_key}-detail"), *DETAIL_TABS.get(resource_key, [])]
    if len(tabs) == 1:
        return []
    return [
        {"label": t.label, "url": reverse(t.url_name, args=[obj.pk]), "active": t.url_name == active_url_name}
        for t in tabs
    ]


def build_table(resource, queryset, exclude=(), limit=25, next_url=None):
    """Rows for a compact table of ``resource`` records (used on detail pages and plan tabs)."""
    columns = [c for c in resource.columns if c.name not in exclude]
    qs = queryset.select_related(*resource.select_related)
    suffix = f"?{urlencode({'next': next_url})}" if next_url else ""
    return {
        "resource": resource,
        "columns": columns,
        "count": qs.count(),
        "rows": [
            {
                "cells": [(c, display.render_value(o, c.name, c.kind)) for c in columns],
                "edit_url": reverse(f"pm:{resource.key}-update", args=[o.pk]) + suffix,
            }
            for o in qs[:limit]
        ],
    }


class DashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = "pm/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_nav"] = "dashboard"
        inactive = [Project.Status.COMPLETE, Project.Status.CANCELLED]
        live_pos = PurchaseOrder.objects.exclude(status=PurchaseOrder.Status.CANCELLED)
        billed = Invoice.objects.exclude(status=Invoice.Status.REJECTED)

        committed = live_pos.aggregate(t=Coalesce(Sum("amount"), ZERO))["t"]
        invoiced = billed.aggregate(t=Coalesce(Sum("amount"), ZERO))["t"]
        paid = billed.filter(status=Invoice.Status.PAID).aggregate(t=Coalesce(Sum("amount"), ZERO))["t"]
        pending = Invoice.objects.filter(
            status__in=[Invoice.Status.RECEIVED, Invoice.Status.UNDER_REVIEW, Invoice.Status.APPROVED]
        )

        ctx["stats"] = [
            {
                "label": "Active projects",
                "value": Project.objects.exclude(status__in=inactive).count(),
                "sub": f"of {Project.objects.count()} total",
                "url": reverse("pm:project-list"),
            },
            {
                "label": "Committed (POs)",
                "value": display.money(committed),
                "sub": f"{live_pos.count()} purchase orders",
                "url": reverse("pm:purchaseorder-list"),
            },
            {
                "label": "Invoiced",
                "value": display.money(invoiced),
                "sub": f"{display.money(paid)} paid",
                "url": reverse("pm:invoice-list"),
            },
            {
                "label": "Invoices pending",
                "value": pending.count(),
                "sub": f"{display.money(pending.aggregate(t=Coalesce(Sum('amount'), ZERO))['t'])} awaiting payment",
                "url": reverse("pm:invoice-list"),
            },
        ]

        # Projects by status, in the order the choices are declared.
        counts = dict(Project.objects.values_list("status").annotate(n=Count("id")))
        total = sum(counts.values()) or 1
        ctx["status_breakdown"] = [
            {"value": value, "label": label, "count": counts.get(value, 0), "pct": 100 * counts.get(value, 0) / total}
            for value, label in Project.Status.choices
        ]
        type_counts = dict(Project.objects.values_list("project_type").annotate(n=Count("id")))
        ctx["type_breakdown"] = [
            {"label": label, "count": type_counts.get(value, 0)} for value, label in Project.ProjectType.choices
        ]

        # Budget burn: the projects with the largest commitments.
        ctx["spend"] = []
        top = (
            Project.objects.annotate(
                committed=Coalesce(
                    Sum("purchase_orders__amount", filter=~Q(purchase_orders__status=PurchaseOrder.Status.CANCELLED)),
                    ZERO,
                )
            )
            .filter(committed__gt=0)
            .order_by("-committed")[:6]
        )
        for project in top:
            spent = billed.filter(purchase_order__project=project).aggregate(t=Coalesce(Sum("amount"), ZERO))["t"]
            pct = float(spent / project.committed * 100) if project.committed else 0
            ctx["spend"].append(
                {
                    "project": project,
                    "committed": display.money(project.committed),
                    "spent": display.money(spent),
                    "pct": min(pct, 100),
                    "pct_label": f"{pct:.0f}%",
                    "over": pct > 100,
                }
            )

        ctx["recent_reports"] = FieldReport.objects.select_related("project")[:5]
        ctx["recent_documents"] = Document.objects.all()[:5]
        ctx["pending_invoices"] = pending.select_related("vendor", "purchase_order").order_by("invoice_date")[:6]
        ctx["panels"] = [panel for panel in (fn(self.request) for fn in DASHBOARD_PANELS) if panel]
        return ctx


class ResourceMixin(LoginRequiredMixin):
    """Resolve the :class:`~pm.resources.Resource` for this view."""

    resource_key = None

    def dispatch(self, request, *args, **kwargs):
        self.resource = REGISTRY[self.resource_key]
        self.model = self.resource.model
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.select_related(*self.resource.select_related)

    def get_template_names(self):
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["resource"] = self.resource
        ctx["active_nav"] = self.resource.key
        return ctx

    def url(self, action, *args):
        return reverse(f"pm:{self.resource.key}-{action}", args=args)


class ResourceListView(ResourceMixin, generic.ListView):
    template_name = "pm/resource_list.html"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        self.filterset = self.resource.filterset_class(self.request.GET or None, queryset=qs)
        for name, field in self.filterset.form.fields.items():
            field.widget.attrs["class"] = INPUT_CLASSES
            if name.endswith(("_after", "_before")):
                field.widget.input_type = "date"
        qs = self.filterset.qs if self.filterset.is_bound and self.filterset.is_valid() else qs

        self.query = self.request.GET.get("q", "").strip()
        if self.query and self.resource.search_fields:
            qs = qs.filter(reduce(or_, (Q(**{f"{f}__icontains": self.query}) for f in self.resource.search_fields)))

        # Sorting is limited to the displayed columns: ?o=amount or ?o=-amount.
        sortable = {c.name for c in self.resource.columns} & {f.name for f in self.model._meta.concrete_fields}
        self.ordering_param = self.request.GET.get("o", "")
        if self.ordering_param.lstrip("-") in sortable:
            qs = qs.order_by(self.ordering_param)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        params.pop("o", None)
        ctx["sort_querystring"] = params.urlencode()
        ctx.update(
            filter_form=self.filterset.form,
            has_filters=bool(self.filterset.form.fields),
            query=self.query,
            ordering=self.ordering_param,
            columns=self.resource.columns,
            rows=[
                (obj, [(c, display.render_value(obj, c.name, c.kind)) for c in self.resource.columns])
                for obj in ctx["object_list"]
            ],
            create_url=self.url("create"),
        )
        return ctx


class ResourceDetailView(ResourceMixin, generic.DetailView):
    template_name = "pm/resource_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        names = self.resource.detail_fields or [
            f.name for f in self.model._meta.concrete_fields if f.name not in {"id", "created_at", "updated_at"}
        ]
        fields = [self.model._meta.get_field(n) for n in names]
        ctx["fields"] = [
            {
                "label": f.verbose_name[:1].upper() + f.verbose_name[1:],
                "value": display.render_value(obj, f.name, display.infer_kind(f)),
                "wide": isinstance(f, models.TextField),
            }
            for f in fields
        ]
        here = self.request.path
        ctx["related_tables"] = []
        for rel in self.resource.related:
            child = REGISTRY[rel.resource]
            table = build_table(child, getattr(obj, rel.accessor).all(), exclude=[rel.fk_name], next_url=here)
            table["add_url"] = f"{reverse(f'pm:{child.key}-create')}?{urlencode({rel.fk_name: obj.pk, 'next': here})}"
            table["all_url"] = f"{reverse(f'pm:{child.key}-list')}?{rel.fk_name}={obj.pk}"
            ctx["related_tables"].append(table)
        ctx["tabs"] = detail_tabs(self.resource.key, obj, f"pm:{self.resource.key}-detail")
        ctx["edit_url"] = self.url("update", obj.pk)
        ctx["delete_url"] = self.url("delete", obj.pk)
        ctx["list_url"] = self.url("list")
        return ctx


class ResourceFormMixin(ResourceMixin):
    template_name = "pm/resource_form.html"

    def get_form_class(self):
        return self.resource.form_class

    def get_success_url(self):
        # ?next= lets callers (e.g. the project Plan tab) bring the user back where they started.
        return safe_next(self.request) or super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        verb = "updated" if self.is_update else "created"
        messages.success(self.request, f"{self.resource.verbose_name} “{self.object}” {verb}.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["is_update"] = self.is_update
        ctx["cancel_url"] = safe_next(self.request) or (
            self.object.get_absolute_url() if self.is_update else self.url("list")
        )
        return ctx


class ResourceCreateView(ResourceFormMixin, generic.CreateView):
    is_update = False

    def get_initial(self):
        # Allow ?project=<uuid> etc. to pre-fill fields (used by "Add" buttons on detail pages).
        initial = super().get_initial()
        form_fields = self.resource.form_class.Meta.fields
        initial.update({k: v for k, v in self.request.GET.items() if k in form_fields})
        return initial


class ResourceUpdateView(ResourceFormMixin, generic.UpdateView):
    is_update = True


class ResourceDeleteView(ResourceMixin, generic.DeleteView):
    template_name = "pm/resource_confirm_delete.html"

    def get_success_url(self):
        return safe_next(self.request) or self.url("list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = safe_next(self.request) or self.object.get_absolute_url()
        return ctx

    def form_valid(self, form):
        name = str(self.object)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                f"“{name}” can't be deleted because other records reference it. Remove or reassign those first.",
            )
            return redirect(self.object.get_absolute_url())
        messages.success(self.request, f"{self.resource.verbose_name} “{name}” deleted.")
        return response
