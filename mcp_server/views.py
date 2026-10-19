"""
The MCP endpoint (``/mcp/``, Streamable HTTP transport answering with plain JSON)
and the "Agent Access" page where a signed-in user manages the token agents use.

Every MCP request must carry the user's API token as ``Authorization: Bearer <key>``
(or DRF's ``Token <key>``). Session cookies are deliberately ignored: the endpoint
is CSRF-exempt, so accepting them would let any web page act as a signed-in user.
"""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View, generic
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.renderers import JSONRenderer

from . import tools

logger = logging.getLogger(__name__)

PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26"]  # newest first
SERVER_INFO = {"name": "projecthub", "title": "ProjectHub", "version": "1.0.0"}
INSTRUCTIONS = (
    "ProjectHub manages a water/wastewater utility's capital projects: projects, vendors, purchase orders, "
    "invoices, field reports, documents, contacts, compliance units, project plans (objectives, risks, "
    "stakeholders, milestones, communication items), activity notes, budgets and permits with compliance "
    "milestones. Call list_resources, then describe_resource before creating or filtering. Records are "
    "identified by UUID; money is a decimal string; dates are YYYY-MM-DD; fiscal years run Oct 1 - Sep 30. "
    "You can read, create and edit records; deleting is not available."
)

# JSON-RPC error codes
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602


def authenticate(request):
    """(user, token) for a valid ``Bearer``/``Token`` header, else None. Inactive users are refused."""
    keyword, _, key = request.headers.get("Authorization", "").partition(" ")
    if keyword.lower() not in {"bearer", "token"} or not key.strip():
        return None
    try:
        return TokenAuthentication().authenticate_credentials(key.strip())
    except AuthenticationFailed:
        return None


def origin_allowed(request):
    """Browsers send Origin; only our own site (or a configured trusted origin) may call in (DNS rebinding)."""
    origin = request.headers.get("Origin")
    if not origin:
        return True
    own = f"{request.scheme}://{request.get_host()}"
    return origin == own or origin in settings.CSRF_TRUSTED_ORIGINS


def rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def to_json(data):
    return JSONRenderer().render(data).decode()


@method_decorator(csrf_exempt, name="dispatch")
class MCPView(View):
    """JSON-RPC over HTTP POST. GET (server-initiated SSE streams) isn't offered, per the spec's 405 option."""

    http_method_names = ["post", "get", "delete", "options"]

    def get(self, request):
        return HttpResponse(status=405, headers={"Allow": "POST"})

    delete = get

    def post(self, request):
        if not origin_allowed(request):
            return JsonResponse(rpc_error(None, INVALID_REQUEST, "Origin not allowed."), status=403)
        auth = authenticate(request)
        if auth is None:
            response = JsonResponse(
                rpc_error(None, INVALID_REQUEST, "Authentication required: send 'Authorization: Bearer <API token>'. "
                          "Create a token on the Agent Access page."),
                status=401,
            )
            response["WWW-Authenticate"] = 'Bearer realm="ProjectHub"'
            return response
        user, token = auth

        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return JsonResponse(rpc_error(None, PARSE_ERROR, "Parse error: the body must be JSON."), status=400)

        batch = isinstance(payload, list)
        replies = [r for r in (self.handle(request, user, token, m) for m in (payload if batch else [payload])) if r]
        if not replies:  # only notifications / responses
            return HttpResponse(status=202)
        return JsonResponse(replies if batch else replies[0], safe=False)

    def handle(self, request, user, token, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return rpc_error(None, INVALID_REQUEST, "Invalid JSON-RPC 2.0 message.")
        method, msg_id = message.get("method"), message.get("id")
        if "id" not in message:  # a notification (e.g. notifications/initialized) or a stray response
            return None
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return rpc_error(msg_id, INVALID_PARAMS, "'params' must be an object.")

        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return rpc_result(msg_id, {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            })
        if method == "ping":
            return rpc_result(msg_id, {})
        if method == "tools/list":
            return rpc_result(msg_id, {"tools": [definition for definition, _ in tools.definitions()]})
        if method == "tools/call":
            return self.call_tool(request, user, token, msg_id, params)
        return rpc_error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")

    def call_tool(self, request, user, token, msg_id, params):
        handlers = {definition["name"]: handler for definition, handler in tools.definitions()}
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in handlers:
            return rpc_error(msg_id, INVALID_PARAMS, f"Unknown tool: {name}")
        if not isinstance(args, dict):
            return rpc_error(msg_id, INVALID_PARAMS, "'arguments' must be an object.")
        logger.info("MCP %s by %s: %s", name, user.get_username(), sorted(args))
        try:
            result = handlers[name](tools.Context(request, user, token), args)
        except tools.ToolError as exc:
            text = str(exc) if exc.detail is None else f"{exc}\n{to_json(exc.detail)}"
            return rpc_result(msg_id, {"content": [{"type": "text", "text": text}], "isError": True})
        content = result.as_content() if isinstance(result, tools.FileResult) else [{"type": "text", "text": to_json(result)}]
        return rpc_result(msg_id, {"content": content, "isError": False})


class AgentAccessView(LoginRequiredMixin, generic.TemplateView):
    """Create, rotate or revoke the signed-in user's API token, with the commands to connect an agent."""

    template_name = "mcp_server/access.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = Token.objects.filter(user=self.request.user).first()
        ctx.update(
            active_nav="agentaccess",
            token=token,
            new_key=self.request.session.pop("mcp_new_token", None),
            mcp_url=self.request.build_absolute_uri("/mcp/"),
            tools=[definition for definition, _ in tools.definitions()],
        )
        return ctx

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        if request.POST.get("action") == "revoke":
            messages.success(request, "Token revoked. Agents and scripts using it can no longer connect.")
        else:
            # The key is shown once, on the next page load, then only its first characters.
            request.session["mcp_new_token"] = Token.objects.create(user=request.user).key
            messages.success(request, "New token created. Copy it now — it won't be shown in full again.")
        return redirect("mcp_server:access")
