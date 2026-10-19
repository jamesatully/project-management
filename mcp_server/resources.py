"""
The REST resources the MCP tools work on, discovered from each installed app's
``<app>.api.urls.router`` so a new app's API shows up here without changes.

Tools never touch models directly: :func:`call` runs the resource's DRF viewset
for the authenticated user, so agents get exactly the API's validation, filters,
pagination and permissions.
"""
import base64
import inspect
from dataclasses import dataclass
from functools import cache
from importlib import import_module
from importlib.util import find_spec

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django_filters import filters as df
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

FACTORY = APIRequestFactory()


@dataclass(frozen=True)
class ApiResource:
    name: str  # the API path segment, e.g. "purchase-orders"
    viewset: type

    @property
    def model(self):
        return self.viewset.queryset.model

    @property
    def label(self):
        return str(self.model._meta.verbose_name_plural).capitalize()

    @property
    def path(self):
        return f"/api/{self.name}/"


@cache
def registry():
    """API path segment -> :class:`ApiResource`, in app and router order."""
    found = {}
    for config in apps.get_app_configs():
        module_name = f"{config.name}.api.urls"
        if not find_spec_safe(module_name):
            continue
        router = getattr(import_module(module_name), "router", None)
        for prefix, viewset, _basename in getattr(router, "registry", []):
            found[prefix] = ApiResource(prefix, viewset)
    return found


def find_spec_safe(module_name):
    try:
        return find_spec(module_name)
    except ModuleNotFoundError:  # the app has no ``api`` package
        return None


def resource_for_model(model):
    for resource in registry().values():
        if resource.model is model:
            return resource.name
    return None


def call(http_request, user, token, view, method="get", pk=None, params=None, data=None, fmt="json"):
    """Run the DRF ``view`` (an ``as_view()`` callable) as ``user`` and return its response."""
    path = "/mcp/internal/"
    extra = {"HTTP_HOST": http_request.get_host(), "secure": http_request.is_secure()}
    if method == "get":
        request = FACTORY.get(path, params or {}, **extra)
    else:
        request = getattr(FACTORY, method)(path, data or {}, format=fmt, **extra)
    force_authenticate(request, user=user, token=token)
    return view(request, **({"pk": pk} if pk is not None else {}))


def upload(file_name, content_base64):
    return SimpleUploadedFile(file_name, base64.b64decode(content_base64, validate=True))


# --- Describing a resource ----------------------------------------------------


def describe(resource):
    """Fields (with types, choices and whether they're writable), filters, search and ordering for agents."""
    viewset = resource.viewset
    serializer = viewset.serializer_class()
    filterset = getattr(viewset, "filterset_class", None)
    extra_actions = [a.url_path for a in viewset.get_extra_actions()]
    return {
        "resource": resource.name,
        "label": resource.label,
        "description": inspect.cleandoc(viewset.__doc__ or resource.model.__doc__ or ""),
        "fields": {name: describe_field(field) for name, field in serializer.fields.items()},
        "filters": {name: describe_filter(f) for name, f in filterset.base_filters.items()} if filterset else {},
        "search_covers": list(getattr(viewset, "search_fields", [])),
        "ordering_fields": list(getattr(viewset, "ordering_fields", [])),
        "extra_actions": extra_actions,
    }


FIELD_TYPES = [
    (serializers.ManyRelatedField, "list of record ids"),
    (serializers.PrimaryKeyRelatedField, "record id"),
    (serializers.ChoiceField, "choice"),
    (serializers.BooleanField, "boolean"),
    (serializers.IntegerField, "integer"),
    (serializers.DecimalField, "decimal string, e.g. \"1250.00\""),
    (serializers.DateTimeField, "datetime (ISO 8601)"),
    (serializers.DateField, "date (YYYY-MM-DD)"),
    (serializers.TimeField, "time (HH:MM)"),
    (serializers.EmailField, "email"),
    (serializers.URLField, "url"),
    (serializers.FileField, "file (use attach_document_file)"),
    (serializers.UUIDField, "uuid"),
    (serializers.JSONField, "json"),
    (serializers.CharField, "string"),
]


def describe_field(field):
    if isinstance(field, serializers.ListSerializer):
        return {
            "type": "list of objects",
            **({"read_only": True} if field.read_only else {"required": field.required}),
            "items": {name: describe_field(f) for name, f in field.child.fields.items()},
            **({"help": inspect.cleandoc(field.child.__doc__)} if field.child.__doc__ else {}),
        }
    if isinstance(field, serializers.Serializer):
        return {
            "type": "object",
            **({"read_only": True} if field.read_only else {"required": field.required}),
            "fields": {name: describe_field(f) for name, f in field.fields.items()},
        }
    kind = next((label for cls, label in FIELD_TYPES if isinstance(field, cls)), "value")
    info = {"type": kind}
    if field.read_only:
        info["read_only"] = True
    else:
        info["required"] = field.required
        if getattr(field, "allow_null", False):
            info["nullable"] = True
    if isinstance(field, serializers.ChoiceField):
        info["choices"] = {str(k): str(v) for k, v in field.choices.items()}
    related = getattr(field, "queryset", None)
    if isinstance(field, serializers.ManyRelatedField):
        related = field.child_relation.queryset
    if related is not None:
        info["resource"] = resource_for_model(related.model)
    if field.label and str(field.label) != field.field_name.replace("_", " ").capitalize():
        info["label"] = str(field.label)
    if field.help_text:
        info["help"] = str(field.help_text)
    return info


def describe_filter(f):
    if isinstance(f, df.ModelChoiceFilter):
        info = {"type": "record id", "resource": resource_for_model(f.queryset.model)}
    elif isinstance(f, df.UUIDFilter):
        info = {"type": "record id"}
    elif isinstance(f, df.ChoiceFilter):
        choices = f.extra.get("choices") or []
        if callable(choices):
            choices = choices()
        info = {"type": "choice", "choices": {str(k): str(v) for k, v in choices}}
    elif isinstance(f, df.BooleanFilter):
        info = {"type": "boolean"}
    elif isinstance(f, df.DateFilter):
        info = {"type": "date (YYYY-MM-DD)"}
    elif isinstance(f, df.NumberFilter):
        info = {"type": "number"}
    else:
        info = {"type": "string"}
    if f.label:
        info["label"] = str(f.label)
    return info
