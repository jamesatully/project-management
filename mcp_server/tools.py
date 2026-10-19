"""
MCP tools: read, create and edit every API resource, plus the program budget
report, document files and starting a budget's next version.

There is deliberately no delete tool — agents can read, write and edit, but
removing records stays a person's job in the web UI or REST API.

Each handler takes a :class:`Context` and the tool's arguments and returns
JSON-serialisable data, or raises :class:`ToolError` with a message the agent
can act on (validation errors, unknown ids, bad arguments).
"""
import base64
import binascii
from dataclasses import dataclass

from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework.authtoken.models import Token

from . import resources

MAX_FILE_BYTES = 10 * 1024 * 1024  # download/upload limit for document files (base64 grows it by a third)


class ToolError(Exception):
    """A tool failure reported back to the agent as ``isError`` with this message/detail."""

    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail


@dataclass
class Context:
    request: object  # the incoming MCP HttpRequest (for host/scheme of absolute URLs)
    user: AbstractBaseUser
    token: Token

    def call(self, viewset, actions, **kwargs):
        """Run one action of a resource's viewset, e.g. ``{"get": "list"}``."""
        return self.run(viewset.as_view(actions), **kwargs)

    def run(self, view, **kwargs):
        return resources.call(self.request, self.user, self.token, view, **kwargs)


# --- Helpers ------------------------------------------------------------------


def get_resource(args):
    name = args.get("resource")
    registry = resources.registry()
    if name not in registry:
        raise ToolError(f"Unknown resource {name!r}. Choose one of: {', '.join(registry)}.")
    return registry[name]


def require(args, key, kind=str):
    value = args.get(key)
    if not isinstance(value, kind) or (isinstance(value, str) and not value.strip()):
        raise ToolError(f"Missing or invalid argument {key!r}.")
    return value


def checked(response, ok=(200, 201)):
    """The response data, or a ToolError carrying the API's error detail (e.g. field-keyed validation errors)."""
    if response.status_code in ok:
        return response.data
    if response.status_code == 404:
        raise ToolError("Not found. Check the record id (a UUID) and resource name.")
    raise ToolError(f"The request was rejected (HTTP {response.status_code}).", response.data)


def query_params(resource, args):
    filters = args.get("filters") or {}
    if not isinstance(filters, dict):
        raise ToolError("'filters' must be an object of {filter name: value}.")
    filterset = getattr(resource.viewset, "filterset_class", None)
    allowed = set(filterset.base_filters) if filterset else set()
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise ToolError(
            f"Unknown filter(s) for {resource.name}: {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(allowed)) or 'none'} (see describe_resource)."
        )
    params = {key: param_value(value) for key, value in filters.items() if value is not None}
    for key in ("search", "ordering"):
        if args.get(key):
            params[key] = str(args[key])
    if args.get("page") is not None:
        params["page"] = page_number(args)
    return params


def page_number(args):
    page = args.get("page", 1)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ToolError("'page' must be a whole number from 1.")
    return page


def param_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return [param_value(v) for v in value]
    return str(value)


# --- Handlers -----------------------------------------------------------------


def list_resources(ctx, args):
    return [
        {"resource": r.name, "label": r.label, "extra_actions": [a.url_path for a in r.viewset.get_extra_actions()]}
        for r in resources.registry().values()
    ]


def describe_resource(ctx, args):
    return resources.describe(get_resource(args))


def list_records(ctx, args):
    resource = get_resource(args)
    data = checked(ctx.call(resource.viewset, {"get": "list"}, params=query_params(resource, args)))
    return {
        "count": data["count"],
        "page": page_number(args),
        "has_more": bool(data["next"]),
        "results": data["results"],
    }


def get_record(ctx, args):
    resource = get_resource(args)
    return checked(ctx.call(resource.viewset, {"get": "retrieve"}, pk=require(args, "id")))


def create_record(ctx, args):
    resource = get_resource(args)
    data = require(args, "data", dict)
    return checked(ctx.call(resource.viewset, {"post": "create"}, method="post", data=data))


def update_record(ctx, args):
    resource = get_resource(args)
    data = require(args, "data", dict)
    return checked(
        ctx.call(resource.viewset, {"patch": "partial_update"}, method="patch", pk=require(args, "id"), data=data)
    )


def program_budget(ctx, args):
    from budgets.api.views import ProgramBudgetView

    params = {k: str(args[k]) for k in ("cycle", "basis", "program") if args.get(k) not in (None, "")}
    return checked(ctx.run(ProgramBudgetView.as_view(), params=params))


def start_next_budget_version(ctx, args):
    viewset = resources.registry()["budgets"].viewset
    return checked(ctx.call(viewset, {"post": "new_version"}, method="post", pk=require(args, "id")))


def get_document_file(ctx, args):
    viewset = resources.registry()["documents"].viewset
    document = checked(ctx.call(viewset, {"get": "retrieve"}, pk=require(args, "id")))
    response = ctx.call(viewset, {"get": "download"}, pk=args["id"])
    if response.status_code != 200:
        raise ToolError("This document has no file attached (or the file is missing from storage).")
    try:
        content = b"".join(response.streaming_content)
    finally:
        # Close only the file: response.close() would send request_finished and drop the DB connection mid-request.
        response.file_to_stream.close()
    if len(content) > MAX_FILE_BYTES:
        raise ToolError(f"The file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB; download it from {document['file']}.")
    return FileResult(
        name=document["file_name"],
        mime_type=response.get("Content-Type", "application/octet-stream"),
        uri=document["file"],
        content=content,
    )


def attach_document_file(ctx, args):
    viewset = resources.registry()["documents"].viewset
    file_name = require(args, "file_name")
    encoded = require(args, "content_base64")
    if len(encoded) > MAX_FILE_BYTES * 4 // 3 + 4:
        raise ToolError(f"Files are limited to {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    try:
        upload = resources.upload(file_name, encoded)
    except (binascii.Error, ValueError):
        raise ToolError("'content_base64' isn't valid base64.")
    return checked(
        ctx.call(viewset, {"patch": "partial_update"}, method="patch", pk=require(args, "id"),
                 data={"file": upload}, fmt="multipart")
    )


def whoami(ctx, args):
    contact = getattr(ctx.user, "contact", None)
    return {
        "username": ctx.user.get_username(),
        "full_name": ctx.user.get_full_name(),
        "is_staff": ctx.user.is_staff,
        "contact": {"id": str(contact.pk), "name": contact.name} if contact else None,
    }


@dataclass
class FileResult:
    """A document file, returned to the agent as an embedded MCP resource."""

    name: str
    mime_type: str
    uri: str
    content: bytes

    def as_content(self):
        resource = {"uri": self.uri, "mimeType": self.mime_type}
        if self.mime_type.startswith("text/") or self.mime_type in {"application/json", "text/csv"}:
            try:
                resource["text"] = self.content.decode("utf-8")
            except UnicodeDecodeError:
                resource["blob"] = base64.b64encode(self.content).decode()
        else:
            resource["blob"] = base64.b64encode(self.content).decode()
        return [{"type": "text", "text": f"{self.name} ({len(self.content)} bytes, {self.mime_type})"},
                {"type": "resource", "resource": resource}]


# --- Definitions --------------------------------------------------------------

READ = {"readOnlyHint": True, "openWorldHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False}
EDIT = {**WRITE, "idempotentHint": True}

RESOURCE_ARG = {"type": "string", "description": "API resource name from list_resources, e.g. \"projects\"."}
ID_ARG = {"type": "string", "description": "The record's id (a UUID)."}


def resource_arg():
    return {**RESOURCE_ARG, "enum": list(resources.registry())}


def definitions():
    """(tool definition, handler) pairs; built lazily because the resource enum needs the app registry."""
    return [
        (
            {
                "name": "list_resources",
                "title": "List resources",
                "description": "List every kind of record in ProjectHub (projects, purchase orders, invoices, "
                "plans, risks, budgets, permits, ...) by API resource name. Start here.",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": READ,
            },
            list_resources,
        ),
        (
            {
                "name": "describe_resource",
                "title": "Describe a resource",
                "description": "A resource's fields (type, required, read-only, valid choices, linked resource), "
                "filters, search coverage and ordering fields. Check this before creating or filtering records.",
                "inputSchema": {"type": "object", "properties": {"resource": resource_arg()}, "required": ["resource"]},
                "annotations": READ,
            },
            describe_resource,
        ),
        (
            {
                "name": "list_records",
                "title": "List or search records",
                "description": "List a resource's records, 50 per page, with optional filters (see "
                "describe_resource), free-text search and ordering (a field name, '-' prefix for descending). "
                "Returns count, page, has_more and results.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "resource": resource_arg(),
                        "filters": {
                            "type": "object",
                            "description": "Filter name -> value, e.g. {\"status\": \"OPEN\", \"project\": \"<uuid>\"}.",
                            "additionalProperties": True,
                        },
                        "search": {"type": "string", "description": "Free-text search."},
                        "ordering": {"type": "string", "description": "e.g. \"-amount\"."},
                        "page": {"type": "integer", "minimum": 1},
                    },
                    "required": ["resource"],
                },
                "annotations": READ,
            },
            list_records,
        ),
        (
            {
                "name": "get_record",
                "title": "Get a record",
                "description": "One record by id, with readable companions like vendor_name and status_display.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"resource": resource_arg(), "id": ID_ARG},
                    "required": ["resource", "id"],
                },
                "annotations": READ,
            },
            get_record,
        ),
        (
            {
                "name": "create_record",
                "title": "Create a record",
                "description": "Create a record. 'data' holds writable fields from describe_resource; links to "
                "other records are ids. Business rules are enforced and field-keyed errors returned on failure.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "resource": resource_arg(),
                        "data": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["resource", "data"],
                },
                "annotations": WRITE,
            },
            create_record,
        ),
        (
            {
                "name": "update_record",
                "title": "Edit a record",
                "description": "Change some fields of a record (a partial update; fields left out are kept). "
                "Same validation as create_record.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "resource": resource_arg(),
                        "id": ID_ARG,
                        "data": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["resource", "id", "data"],
                },
                "annotations": EDIT,
            },
            update_record,
        ),
        (
            {
                "name": "get_program_budget",
                "title": "Program budget report",
                "description": "Project budgets rolled up by program, fiscal year and category for one budget "
                "cycle (fiscal years run Oct 1 - Sep 30).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cycle": {"type": "integer", "description": "Budget cycle fiscal year; default current."},
                        "basis": {"type": "string", "enum": ["adopted", "proposed"], "description": "Default adopted."},
                        "program": {"type": "string", "description": "A project type, e.g. CIP_RR; default all."},
                    },
                },
                "annotations": READ,
            },
            program_budget,
        ),
        (
            {
                "name": "start_next_budget_version",
                "title": "Start next budget version",
                "description": "Copy a budget's line items and amounts into a new draft for the next budget cycle "
                "(refused if the project already has one).",
                "inputSchema": {"type": "object", "properties": {"id": {**ID_ARG, "description": "The budget id."}},
                                "required": ["id"]},
                "annotations": WRITE,
            },
            start_next_budget_version,
        ),
        (
            {
                "name": "get_document_file",
                "title": "Download a document's file",
                "description": "The file attached to a document (text inline, other types base64), up to 10 MB.",
                "inputSchema": {"type": "object", "properties": {"id": {**ID_ARG, "description": "The document id."}},
                                "required": ["id"]},
                "annotations": READ,
            },
            get_document_file,
        ),
        (
            {
                "name": "attach_document_file",
                "title": "Attach a file to a document",
                "description": "Upload a file (base64, up to 10 MB) to a document, replacing any existing file. "
                "To remove a file, update_record the document with {\"file\": null}.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {**ID_ARG, "description": "The document id."},
                        "file_name": {"type": "string", "description": "e.g. DMR-2026-09.pdf"},
                        "content_base64": {"type": "string"},
                    },
                    "required": ["id", "file_name", "content_base64"],
                },
                "annotations": EDIT,
            },
            attach_document_file,
        ),
        (
            {
                "name": "whoami",
                "title": "Current user",
                "description": "The signed-in user the agent acts as, and their linked contact (if any).",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": READ,
            },
            whoami,
        ),
    ]
