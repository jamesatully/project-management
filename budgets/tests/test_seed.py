from io import StringIO

from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase

from ..models import Budget, BudgetAmount


class BudgetSeedTests(TestCase):
    def test_seed_demo_includes_budget_history(self):
        call_command("seed_demo", "--projects", "15", "--today", "2026-06-30", stdout=StringIO())
        self.assertTrue(BudgetAmount.objects.exists())
        statuses = set(Budget.objects.values_list("status", flat=True))
        self.assertTrue({"APPROVED", "SUPERSEDED"} <= statuses)
        # FY2027 versions are still being prepared on June 30, 2026.
        self.assertTrue(Budget.objects.filter(budget_year=2027, status__in=["DRAFT", "SUBMITTED"]).exists())
        self.assertFalse(
            Budget.objects.filter(status="APPROVED").values("project").annotate(n=Count("id")).filter(n__gt=1).exists()
        )
        for budget in Budget.objects.filter(status="SUPERSEDED").select_related("superseded_by")[:50]:
            self.assertGreater(budget.superseded_by.budget_year, budget.budget_year)
