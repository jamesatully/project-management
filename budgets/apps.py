from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "budgets"
    verbose_name = "Budgets"

    def ready(self):
        # Plug budget pages, the project tab, the dashboard panel and demo data into the pm app.
        from . import demo, resources  # noqa: F401
