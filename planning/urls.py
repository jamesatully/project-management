from django.urls import path

from . import views

app_name = "planning"

urlpatterns = [
    path("projects/<uuid:pk>/plan/", views.ProjectPlanView.as_view(), name="project-plan"),
    path("projects/<uuid:pk>/activity/", views.ProjectActivityView.as_view(), name="project-activity"),
]
