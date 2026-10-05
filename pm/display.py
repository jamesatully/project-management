"""
Helpers that turn model values into HTML snippets for tables and detail pages.
"""
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.template.defaultfilters import date as date_filter
from django.template.defaultfilters import linebreaksbr
from django.utils.html import format_html

EMPTY = format_html('<span class="text-bodydark2">—</span>')

# Status value -> badge colour. Anything not listed renders grey.
STATUS_COLORS = {
    "PLANNING": "sky",
    "DESIGN": "indigo",
    "CONSTRUCTION": "amber",
    "ON_HOLD": "orange",
    "COMPLETE": "emerald",
    "CANCELLED": "slate",
    "DRAFT": "slate",
    "OPEN": "sky",
    "CLOSED": "emerald",
    "RECEIVED": "sky",
    "UNDER_REVIEW": "amber",
    "APPROVED": "indigo",
    "PAID": "emerald",
    "REJECTED": "rose",
}

BADGE_CLASSES = {
    "sky": "bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-500/10 dark:text-sky-300",
    "indigo": "bg-indigo-50 text-indigo-700 ring-indigo-600/20 dark:bg-indigo-500/10 dark:text-indigo-300",
    "amber": "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300",
    "orange": "bg-orange-50 text-orange-700 ring-orange-600/20 dark:bg-orange-500/10 dark:text-orange-300",
    "emerald": "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300",
    "rose": "bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-300",
    "slate": "bg-slate-100 text-slate-700 ring-slate-500/20 dark:bg-slate-500/10 dark:text-slate-300",
}


def money(value):
    if value is None:
        return EMPTY
    return f"${value:,.2f}"


def status_badge(obj, name):
    value = getattr(obj, name)
    label = getattr(obj, f"get_{name}_display")()
    classes = BADGE_CLASSES[STATUS_COLORS.get(value, "slate")]
    return format_html(
        '<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset {}">{}</span>',
        classes,
        label,
    )


def score_badge(score):
    """Badge for a likelihood x impact risk score (1-25): low < 8 <= medium < 15 <= high."""
    if score >= 15:
        color, label = "rose", "High"
    elif score >= 8:
        color, label = "amber", "Medium"
    else:
        color, label = "emerald", "Low"
    return format_html(
        '<span class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset {}">'
        '<span class="tabular-nums">{}</span> · {}</span>',
        BADGE_CLASSES[color],
        score,
        label,
    )


def infer_kind(field):
    """Pick a display kind for a model field (used on detail pages)."""
    if isinstance(field, models.ForeignKey):
        return "fk"
    if field.name == "status":
        return "status"
    if field.name == "score":
        return "score"
    if field.name == "amount":
        return "money"
    if isinstance(field, models.DateTimeField):
        return "datetime"
    if isinstance(field, models.DateField):
        return "date"
    if isinstance(field, models.URLField):
        return "url"
    if isinstance(field, models.TextField):
        return "multiline"
    if field.name == "time_on_site":
        return "hours"
    return "text"


def render_value(obj, name, kind="text"):
    """Render ``obj.<name>`` (a model field or a plain attribute/property) as HTML according to ``kind``."""
    if kind == "status":
        return status_badge(obj, name)

    try:
        field = obj._meta.get_field(name)
    except FieldDoesNotExist:
        field = None
    value = getattr(obj, name)
    if value in (None, ""):
        return EMPTY

    if kind == "link":
        text = date_filter(value, "M j, Y") if isinstance(field, models.DateField) else value
        return format_html(
            '<a href="{}" class="font-medium text-primary hover:underline">{}</a>', obj.get_absolute_url(), text
        )
    if kind == "fk":
        return format_html('<a href="{}" class="hover:text-primary hover:underline">{}</a>', value.get_absolute_url(), value)
    if kind == "money":
        return money(value)
    if kind == "date":
        return date_filter(value, "M j, Y")
    if kind == "month":
        return date_filter(value, "M Y")
    if kind == "days":
        if value == 0:
            return "On time"
        return format_html(
            '<span class="{}">{} day{} {}</span>',
            "font-medium text-danger" if value > 30 else "",
            abs(value),
            "" if abs(value) == 1 else "s",
            "late" if value > 0 else "early",
        )
    if kind == "datetime":
        return date_filter(value, "M j, Y g:i A")
    if kind == "score":
        return score_badge(value)
    if kind == "hours":
        return f"{value.normalize():f} h"
    if kind == "url":
        return format_html('<a href="{0}" target="_blank" rel="noopener" class="text-primary hover:underline">{0}</a>', value)
    if kind == "multiline":
        return linebreaksbr(value, autoescape=True)
    if field is not None and field.choices:
        return getattr(obj, f"get_{name}_display")()
    return value
