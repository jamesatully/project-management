from django.urls import reverse

from .resources import REGISTRY


def navigation(request):
    """Sidebar links grouped by ``Resource.nav_group``, in registration order, as ``nav_groups``."""
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
    return {"nav_groups": [{"label": label, "items": items} for label, items in groups.items()]}
