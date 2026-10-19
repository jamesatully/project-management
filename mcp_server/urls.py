from django.urls import path

from . import views

app_name = "mcp_server"

urlpatterns = [
    path("mcp/", views.MCPView.as_view(), name="mcp"),
    path("agent-access/", views.AgentAccessView.as_view(), name="access"),
]
