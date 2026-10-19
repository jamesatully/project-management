from django.apps import AppConfig


class McpServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mcp_server"
    verbose_name = "MCP Server"

    def ready(self):
        # Sidebar link to the Agent Access page (token management and connection instructions).
        from pm.resources import NavLink, register_nav_link

        register_nav_link(NavLink("Developer", "Agent Access", "mcp_server:access", "key", "agentaccess"))
