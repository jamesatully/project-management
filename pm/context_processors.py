from django.urls import reverse

from .resources import NAV_LINKS, REGISTRY

DEVELOPER_GROUP = "Developer"


def navigation(request):
    """
    Sidebar links grouped by ``Resource.nav_group``, in registration order, as ``nav_groups``.
    Registered :class:`~pm.resources.NavLink` entries follow the resources in their group; links in the
    "Developer" group go to the sidebar's Developer section (after API docs and Admin) as ``developer_links``.
    """
    groups = {}
    for key, resource in REGISTRY.items():
        if resource.nav_group:
            groups.setdefault(resource.nav_group, []).append(
                {
                    "key": key,
                    "label": resource.verbose_name_plural,
                    "icon": resource.icon,
                    "url": reverse(f"pm:{key}-list"),
                }
            )
    for link in NAV_LINKS:
        groups.setdefault(link.group, []).append(
            {"key": link.key, "label": link.label, "icon": link.icon, "url": reverse(link.url_name)}
        )
    developer_links = groups.pop(DEVELOPER_GROUP, [])
    return {
        "nav_groups": [{"label": label, "items": items} for label, items in groups.items()],
        "developer_links": developer_links,
    }
