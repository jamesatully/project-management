# MCP server (agent access)

ProjectHub includes a [Model Context Protocol](https://modelcontextprotocol.io)
server so AI agents (Claude Code, Claude Desktop and other MCP clients) can work
with the app's data. It lives in the `mcp_server` app and is served by the same
Django process at **`/mcp/`**.

## Authentication

Every request needs the user's **API token** (the same DRF token as the REST
API) in the `Authorization` header, as `Bearer <key>` or `Token <key>`.
Requests without a valid token for an active user get `401`.

- Get a token from **Developer → Agent Access** in the sidebar
  (`/agent-access/`). The page creates, regenerates or revokes your token and
  shows the full key only once, right after it's created. It also shows the
  connection commands. Regenerating or revoking it disconnects every agent
  and script that uses it.
- Tokens can also be issued as for the API (`POST /api/auth/token/` or
  `manage.py drf_create_token <user>`).
- Browser sessions are **not** accepted. The endpoint is CSRF-exempt, so cookies
  must never be enough to authenticate it.
- Requests carrying an `Origin` header are refused unless it is the site itself
  or listed in `DJANGO_CSRF_TRUSTED_ORIGINS` (protection against DNS rebinding).

The agent acts as the token's user. It can do what that user can do through the
REST API, **except delete**: there is no delete tool. Deleting records stays a
person's job (web UI or REST API). Each tool call is logged (`mcp_server.views`
logger: tool name, username, argument names).

## Connecting

```bash
# Claude Code
claude mcp add --transport http projecthub http://localhost:8000/mcp/ \
  --header "Authorization: Bearer <your token>"
```

```json
{
  "mcpServers": {
    "projecthub": {
      "type": "http",
      "url": "http://localhost:8000/mcp/",
      "headers": {"Authorization": "Bearer <your token>"}
    }
  }
}
```

Keep tokens out of committed files. Use your client's environment-variable
support for the header value.

## Tools

| Tool | Kind | What it does |
|---|---|---|
| `list_resources` | read | Every API resource (`projects`, `purchase-orders`, `risks`, `budgets`, `permits`, ...). |
| `describe_resource` | read | A resource's fields (type, required, read-only, choices, linked resource), filters, search coverage and ordering fields. |
| `list_records` | read | List/search one resource: `filters` (`{name: value}`, the API's filters; unknown names are rejected), `search`, `ordering`, `page` (50 per page). Returns `count`, `page`, `has_more`, `results`. |
| `get_record` | read | One record by UUID. |
| `create_record` | write | Create a record from `data` (writable fields; links as UUIDs). |
| `update_record` | edit | Partial update (`PATCH`) of a record. |
| `get_program_budget` | read | The program budget roll-up (`cycle`, `basis`, `program`), as `GET /api/program-budget/`. |
| `start_next_budget_version` | write | Copy a budget into a new draft for the next cycle, as `POST /api/budgets/<id>/new-version/`. |
| `get_document_file` | read | A document's attached file as an embedded resource (text inline, otherwise base64; up to 10 MB). |
| `attach_document_file` | edit | Upload a base64 file (up to 10 MB) to a document, replacing any existing one. Remove a file with `update_record` and `{"file": null}`. |
| `whoami` | read | The user the agent acts as and their linked contact. |

Read tools are annotated `readOnlyHint`; write tools are non-destructive.

Validation errors come back as tool errors (`isError: true`). Their text holds
the API's field-keyed messages, e.g.
`{"project_id": ["Project ID must look like 2021-2-20-0 (year-#-#-#)."]}`.
Field formats are as in [api.md](api.md): money is a decimal string, dates are
`YYYY-MM-DD`, fiscal years run Oct 1 – Sep 30.

## How it works

- **Transport**: MCP Streamable HTTP. `POST /mcp/` takes JSON-RPC 2.0 (a single
  message or a batch) and answers with `application/json`. Notifications get
  `202`. `GET` and `DELETE` return `405` because the server offers no
  server-initiated streams and keeps no sessions. Supported protocol versions:
  `2025-11-25`, `2025-06-18`, `2025-03-26`.
- **Same rules as the API**: tools don't touch models. They run the resource's
  DRF viewset in-process as the token's user (`mcp_server/resources.py:call`),
  so serializers, `ModelCleanMixin` validation, FilterSets, pagination and
  permissions are exactly the API's.
- **Discovery**: resources come from each installed app's `<app>.api.urls.router`.
  A new app's API therefore appears in the MCP tools automatically, with its
  field and filter descriptions generated from the serializer and FilterSet.
  Only special endpoints (reports, custom actions) need a tool in
  `mcp_server/tools.py`.
- **No dependencies**: the protocol is a small JSON-RPC view (`mcp_server/views.py`);
  it doesn't need the `mcp` Python SDK or an ASGI server.
