"""
Web UI routes. One list/create/detail/update/delete set is generated for each
entry in the resource registry (including resources other apps register), e.g. ``pm:project-list`` → ``/projects/``.
"""
from django.urls import path

from . import views
from .resources import REGISTRY

app_name = "pm"

urlpatterns = [path("", views.DashboardView.as_view(), name="dashboard")]

for key, resource in REGISTRY.items():
    prefix = resource.url_prefix
    urlpatterns += [
        path(f"{prefix}/", views.ResourceListView.as_view(resource_key=key), name=f"{key}-list"),
        path(f"{prefix}/new/", views.ResourceCreateView.as_view(resource_key=key), name=f"{key}-create"),
        path(f"{prefix}/<uuid:pk>/", views.ResourceDetailView.as_view(resource_key=key), name=f"{key}-detail"),
        path(f"{prefix}/<uuid:pk>/edit/", views.ResourceUpdateView.as_view(resource_key=key), name=f"{key}-update"),
        path(f"{prefix}/<uuid:pk>/delete/", views.ResourceDeleteView.as_view(resource_key=key), name=f"{key}-delete"),
    ]
