from django.apps import AppConfig


class PmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pm"
    verbose_name = "Project Management"

    def ready(self):
        from . import signals  # noqa: F401  (connects receivers)
