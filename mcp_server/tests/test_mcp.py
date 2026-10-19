"""The MCP endpoint: authentication, the JSON-RPC protocol, every tool, and the Agent Access page."""
import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from budgets.models import Budget, next_budget_year
from budgets.tests.factories import add_line, make_budget
from pm.models import Project, PurchaseOrder
from pm.tests.factories import make_contact, make_document, make_po, make_project, make_project_manager, make_vendor
from pm.tests.test_document_files import PDF, TempMediaMixin, pdf

from .. import resources, tools

URL = "/mcp/"


class MCPTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("agent-user", password="pw-123456!")
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token.key}"}

    def post(self, payload, **headers):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        return self.client.post(URL, body, content_type="application/json", **{**self.auth, **headers})

    def rpc(self, method, params=None, msg_id=1):
        response = self.post({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def tool(self, name, **arguments):
        """(is_error, parsed JSON or raw text of the first content item)."""
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        text = result["content"][0]["text"]
        try:
            return result["isError"], json.loads(text)
        except ValueError:
            return result["isError"], text


class AuthenticationTests(MCPTestCase):
    def test_requires_a_token(self):
        response = self.client.post(URL, "{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Bearer", response["WWW-Authenticate"])

    def test_rejects_bad_and_malformed_tokens(self):
        for header in ["Bearer nope", "Bearer", "Basic abc", self.token.key]:
            with self.subTest(header=header):
                self.assertEqual(self.post({}, HTTP_AUTHORIZATION=header).status_code, 401)

    def test_accepts_bearer_and_token_keywords(self):
        for keyword in ["Bearer", "Token", "bearer"]:
            with self.subTest(keyword=keyword):
                response = self.post(
                    {"jsonrpc": "2.0", "id": 1, "method": "ping"}, HTTP_AUTHORIZATION=f"{keyword} {self.token.key}"
                )
                self.assertEqual(response.json()["result"], {})

    def test_inactive_user_is_refused(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code, 401)

    def test_session_login_alone_is_not_enough(self):
        # The endpoint is CSRF-exempt, so a browser session must never authenticate it.
        self.client.force_login(self.user)
        response = self.client.post(URL, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_foreign_origin_is_refused(self):
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                   HTTP_ORIGIN="https://evil.example").status_code, 403)
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                   HTTP_ORIGIN="http://testserver").status_code, 200)

    @override_settings(CSRF_TRUSTED_ORIGINS=["https://hub.example"])
    def test_trusted_origin_is_allowed(self):
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                   HTTP_ORIGIN="https://hub.example").status_code, 200)

    def test_revoked_token_stops_working(self):
        self.token.delete()
        self.assertEqual(self.post({"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code, 401)


class ProtocolTests(MCPTestCase):
    def test_initialize_negotiates_version(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "1"}})["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "projecthub")
        self.assertIn("deleting is not available", result["instructions"])
        unknown = self.rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(unknown["protocolVersion"], "2025-11-25")

    def test_notifications_get_202(self):
        response = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b"")

    def test_errors(self):
        self.assertEqual(self.post("{not json").json()["error"]["code"], -32700)
        self.assertEqual(self.post({"id": 1, "method": "ping"}).json()["error"]["code"], -32600)
        self.assertEqual(self.rpc("resources/read")["error"]["code"], -32601)
        self.assertEqual(self.rpc("tools/call", {"name": "delete_record"})["error"]["code"], -32602)

    def test_batch(self):
        response = self.post([{"jsonrpc": "2.0", "id": 1, "method": "ping"},
                              {"jsonrpc": "2.0", "method": "notifications/initialized"},
                              {"jsonrpc": "2.0", "id": 2, "method": "ping"}])
        self.assertEqual([r["id"] for r in response.json()], [1, 2])

    def test_get_and_delete_not_allowed(self):
        self.assertEqual(self.client.get(URL, **self.auth).status_code, 405)
        self.assertEqual(self.client.delete(URL, **self.auth).status_code, 405)

    def test_tools_list_has_no_delete(self):
        tools_ = self.rpc("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools_}
        self.assertTrue({"list_records", "get_record", "create_record", "update_record"} <= names)
        self.assertFalse([n for n in names if "delete" in n])
        for tool in tools_:
            self.assertEqual(tool["inputSchema"]["type"], "object")
            self.assertIn("readOnlyHint", tool["annotations"])


class ResourceDiscoveryTests(MCPTestCase):
    def test_every_api_resource_is_discovered(self):
        expected = {
            "projects", "vendors", "compliance-units", "contacts", "purchase-orders", "invoices", "field-reports",
            "documents", "plans", "objectives", "risks", "stakeholders", "milestones", "communication-items",
            "activity-notes", "budgets", "budget-line-items", "permits", "compliance-milestones",
        }
        self.assertEqual(set(resources.registry()), expected)
        _, listed = self.tool("list_resources")
        self.assertEqual({r["resource"] for r in listed}, expected)

    def test_every_resource_describes(self):
        for name in resources.registry():
            with self.subTest(resource=name):
                is_error, data = self.tool("describe_resource", resource=name)
                self.assertFalse(is_error, data)
                self.assertIn("id", data["fields"])

    def test_describe_details(self):
        _, data = self.tool("describe_resource", resource="purchase-orders")
        self.assertEqual(data["fields"]["vendor"], {"type": "record id", "required": True, "resource": "vendors"})
        self.assertIn("OPEN", data["fields"]["status"]["choices"])
        self.assertTrue(data["fields"]["vendor_name"]["read_only"])
        self.assertIn("status", data["filters"])
        self.assertIn("amount", data["ordering_fields"])
        _, items = self.tool("describe_resource", resource="budget-line-items")
        self.assertEqual(items["fields"]["amounts"]["type"], "list of objects")
        self.assertIn("fiscal_year", items["fields"]["amounts"]["items"])


class ReadToolTests(MCPTestCase):
    def setUp(self):
        super().setUp()
        self.vendor = make_vendor()
        self.project = make_project()
        self.po = make_po(vendor=self.vendor, project=self.project, amount="5000.00")
        make_po(vendor=self.vendor, project=self.project, po_number="4500999", status=PurchaseOrder.Status.CLOSED)

    def test_list_filter_search_order(self):
        _, data = self.tool("list_records", resource="purchase-orders", filters={"status": "OPEN"})
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], str(self.po.pk))
        self.assertFalse(data["has_more"])
        _, data = self.tool("list_records", resource="purchase-orders", search="4500999", ordering="-amount")
        self.assertEqual(data["count"], 1)

    def test_list_rejects_unknown_filters_and_bad_values(self):
        is_error, text = self.tool("list_records", resource="purchase-orders", filters={"colour": "red"})
        self.assertTrue(is_error)
        self.assertIn("colour", text)
        is_error, text = self.tool("list_records", resource="purchase-orders", filters={"status": "PURPLE"})
        self.assertTrue(is_error)
        self.assertIn("valid choice", text)
        is_error, _ = self.tool("list_records", resource="purchase-orders", page=0)
        self.assertTrue(is_error)
        is_error, _ = self.tool("list_records", resource="spaceships")
        self.assertTrue(is_error)

    def test_boolean_filter(self):
        make_contact(user=self.user)
        _, data = self.tool("list_records", resource="contacts", filters={"has_user": True})
        self.assertEqual(data["count"], 1)

    def test_get_record(self):
        _, data = self.tool("get_record", resource="purchase-orders", id=str(self.po.pk))
        self.assertEqual(data["vendor_name"], self.vendor.name)
        is_error, text = self.tool("get_record", resource="purchase-orders", id="not-a-uuid")
        self.assertTrue(is_error)
        self.assertIn("Not found", text)

    def test_program_budget(self):
        budget = make_budget(self.project, 2027, Budget.Status.APPROVED)
        add_line(budget, amounts={2027: "100"})
        _, data = self.tool("get_program_budget", cycle=2027)
        self.assertEqual(data["cycle"], 2027)
        self.assertEqual(data["totals"]["total"], "100.00")
        is_error, text = self.tool("get_program_budget", basis="imagined")
        self.assertTrue(is_error)
        self.assertIn("basis", text)

    def test_whoami(self):
        contact = make_contact(user=self.user, name="Agent Owner")
        _, data = self.tool("whoami")
        self.assertEqual(data["username"], "agent-user")
        self.assertEqual(data["contact"], {"id": str(contact.pk), "name": "Agent Owner"})


class WriteToolTests(MCPTestCase):
    def test_create_runs_model_validation(self):
        pm = make_project_manager()
        data = {"name": "Creek Outfall Repair", "project_id": "bad-id", "budget_id": "6822099",
                "project_type": "CIP_RR", "project_manager": str(pm.pk)}
        is_error, text = self.tool("create_record", resource="projects", data=data)
        self.assertTrue(is_error)
        self.assertIn("project_id", text)
        self.assertFalse(Project.objects.exists())

        is_error, created = self.tool("create_record", resource="projects", data={**data, "project_id": "2026-3-1-0"})
        self.assertFalse(is_error, created)
        self.assertEqual(Project.objects.get().name, "Creek Outfall Repair")
        self.assertEqual(created["project_manager_name"], pm.name)

    def test_update_is_partial(self):
        project = make_project()
        is_error, data = self.tool("update_record", resource="projects", id=str(project.pk), data={"status": "DESIGN"})
        self.assertFalse(is_error, data)
        project.refresh_from_db()
        self.assertEqual(project.status, "DESIGN")
        self.assertEqual(project.name, "Main St Rehab")

    def test_update_validation_error(self):
        project = make_project()
        is_error, text = self.tool("update_record", resource="projects", id=str(project.pk),
                                   data={"project_type": "SPACEPORT"})
        self.assertTrue(is_error)
        self.assertIn("project_type", text)

    def test_nested_write(self):
        budget = make_budget(make_project(), 2028)
        is_error, data = self.tool("create_record", resource="budget-line-items", data={
            "budget": str(budget.pk), "category": "DESIGN",
            "amounts": [{"fiscal_year": 2028, "amount": "1500.00"}],
        })
        self.assertFalse(is_error, data)
        self.assertEqual(data["total"], "1500.00")

    def test_data_must_be_an_object(self):
        is_error, text = self.tool("create_record", resource="vendors", data="Acme")
        self.assertTrue(is_error)
        self.assertIn("data", text)

    def test_start_next_budget_version(self):
        year = next_budget_year()
        source = make_budget(make_project(), year - 1, Budget.Status.APPROVED)
        add_line(source, amounts={year: "250"})
        is_error, data = self.tool("start_next_budget_version", id=str(source.pk))
        self.assertFalse(is_error, data)
        self.assertEqual((data["budget_year"], data["total"]), (year, "250.00"))
        is_error, text = self.tool("start_next_budget_version", id=str(source.pk))
        self.assertTrue(is_error)
        self.assertIn(f"FY{year}", text)

    def test_actions_are_made_as_the_token_user(self):
        # Writes go through the API as this user, so a deactivated user's token can't write either.
        self.assertEqual(tools.Context(None, self.user, self.token).user, self.user)


class DocumentFileToolTests(TempMediaMixin, MCPTestCase):
    def setUp(self):
        super().setUp()
        self.document = make_document(make_project())

    def file_call(self, name, **arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    def test_attach_and_download(self):
        is_error, data = self.tool("attach_document_file", id=str(self.document.pk), file_name="Award.pdf",
                                   content_base64=base64.b64encode(PDF).decode())
        self.assertFalse(is_error, data)
        self.assertEqual(data["file_name"], "Award.pdf")

        result = self.file_call("get_document_file", id=str(self.document.pk))
        self.assertFalse(result["isError"])
        resource = result["content"][1]["resource"]
        self.assertEqual(resource["mimeType"], "application/pdf")
        self.assertEqual(base64.b64decode(resource["blob"]), PDF)
        self.assertTrue(resource["uri"].startswith("http://testserver/api/documents/"))

    def test_attach_validates(self):
        is_error, text = self.tool("attach_document_file", id=str(self.document.pk), file_name="x.pdf",
                                   content_base64="***not base64***")
        self.assertTrue(is_error)
        self.assertIn("base64", text)
        is_error, text = self.tool("attach_document_file", id=str(self.document.pk), file_name="page.html",
                                   content_base64=base64.b64encode(b"<p>hi</p>").decode())
        self.assertTrue(is_error)
        self.assertIn("file", text)

    def test_remove_file_with_update(self):
        self.document.file = pdf()
        self.document.save()
        is_error, data = self.tool("update_record", resource="documents", id=str(self.document.pk),
                                   data={"file": None})
        self.assertFalse(is_error, data)
        self.document.refresh_from_db()
        self.assertFalse(self.document.file)

    def test_download_without_file(self):
        result = self.file_call("get_document_file", id=str(self.document.pk))
        self.assertTrue(result["isError"])


class AgentAccessPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("page-user", password="pw-123456!")
        self.url = reverse("mcp_server:access")

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_create_shows_key_once_then_regenerate_and_revoke(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Create token")
        self.assertContains(response, "Agent Access")  # sidebar link in the Developer section, not a second one
        self.assertEqual(response.content.decode().count(">Developer</p>"), 1)
        self.assertContains(response, "http://testserver/mcp/")

        response = self.client.post(self.url, {"action": "create"}, follow=True)
        key = Token.objects.get(user=self.user).key
        self.assertContains(response, key)
        self.assertNotContains(self.client.get(self.url), key)  # shown once only

        self.client.post(self.url, {"action": "create"})
        self.assertNotEqual(Token.objects.get(user=self.user).key, key)

        self.client.post(self.url, {"action": "revoke"})
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_new_key_works_against_the_endpoint(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"action": "create"})
        key = Token.objects.get(user=self.user).key
        self.client.logout()
        response = self.client.post(URL, json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
                                    content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {key}")
        self.assertEqual(response.status_code, 200)
