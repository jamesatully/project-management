from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compliance"
    verbose_name = "Permit Compliance"

    def ready(self):
        # Plug permit and milestone pages, related tables, the dashboard panel and demo data into the pm app.
        from . import demo, resources  # noqa: F401
