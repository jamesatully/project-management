from django.urls import path

from . import views

app_name = "budgets"

urlpatterns = [
    path("projects/<uuid:pk>/budget/", views.ProjectBudgetView.as_view(), name="project-budget"),
    path("budgets/program/", views.ProgramBudgetView.as_view(), name="program"),
    path("budgets/<uuid:pk>/line-items/", views.BudgetLineItemsView.as_view(), name="line-items"),
    path("budgets/<uuid:pk>/new-version/", views.BudgetCopyView.as_view(), name="copy"),
]
