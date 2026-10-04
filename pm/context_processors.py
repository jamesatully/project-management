from django.urls import reverse

from .resources import REGISTRY

# Sidebar order.
NAV_ORDER = ["project", "purchaseorder", "invoice", "fieldreport", "document", "vendor"]


def navigation(request):
    """Sidebar links, available to every template as ``nav_items``."""
    return {
        "nav_items": [
            {
                "key": key,
                "label": REGISTRY[key].verbose_name_plural,
                "icon": REGISTRY[key].icon,
                "url": reverse(f"pm:{key}-list"),
            }
            for key in NAV_ORDER
        ]
    }
