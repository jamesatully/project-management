from django.apps import AppConfig


class PlanningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "planning"
    verbose_name = "Project Planning"

    def ready(self):
        # Plug planning pages, tabs, dashboard panels and demo data into the pm app.
        from . import demo, resources  # noqa: F401
