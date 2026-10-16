from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("budgets", views.BudgetViewSet)
router.register("budget-line-items", views.BudgetLineItemViewSet)

urlpatterns = [path("program-budget/", views.ProgramBudgetView.as_view(), name="api-program-budget"), *router.urls]
