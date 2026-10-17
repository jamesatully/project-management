import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from pm.tests.factories import make_project

from ..models import Budget, BudgetAmount, BudgetLineItem, fiscal_year, fiscal_year_dates, next_budget_year
from .factories import add_line, make_budget

S = Budget.Status


class FiscalYearTests(TestCase):
    def test_fiscal_year_runs_october_to_september(self):
        self.assertEqual(fiscal_year(datetime.date(2026, 9, 30)), 2026)
        self.assertEqual(fiscal_year(datetime.date(2026, 10, 1)), 2027)
        self.assertEqual(fiscal_year(datetime.date(2027, 1, 15)), 2027)
        self.assertEqual(fiscal_year_dates(2027), (datetime.date(2026, 10, 1), datetime.date(2027, 9, 30)))

    def test_next_budget_cycle(self):
        self.assertEqual(next_budget_year(datetime.date(2026, 10, 16)), 2028)
        self.assertEqual(next_budget_year(datetime.date(2026, 3, 1)), 2027)


class BudgetModelTests(TestCase):
    def setUp(self):
        self.project = make_project()

    def test_approving_supersedes_previous_approved_budget(self):
        old = make_budget(self.project, 2026, S.APPROVED)
        new = make_budget(self.project, 2027)
        new.status, new.approved_by, new.approved_date = S.APPROVED, "Board", datetime.date(2026, 9, 15)
        new.full_clean()  # the one-approved rule mustn't block approving the new version
        new.save()
        old.refresh_from_db()
        self.assertEqual(old.status, S.SUPERSEDED)
        self.assertEqual(old.superseded_by, new)
        self.assertEqual(self.project.budgets.filter(status=S.APPROVED).get(), new)

    def test_database_allows_only_one_approved_budget(self):
        make_budget(self.project, 2026, S.APPROVED)
        other = make_budget(self.project, 2027)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Budget.objects.filter(pk=other.pk).update(status=S.APPROVED)  # bypasses save()

    def test_one_budget_per_cycle(self):
        make_budget(self.project, 2027)
        with self.assertRaises(ValidationError):
            Budget(project=self.project, budget_year=2027).full_clean()

    def test_approved_budget_needs_approver_and_date(self):
        budget = Budget(project=self.project, budget_year=2027, status=S.APPROVED)
        with self.assertRaises(ValidationError) as ctx:
            budget.full_clean()
        self.assertIn("approved_by", ctx.exception.message_dict)
        self.assertIn("approved_date", ctx.exception.message_dict)

    def test_older_cycle_cannot_replace_newer_approved_budget(self):
        make_budget(self.project, 2027, S.APPROVED)
        older = Budget(
            project=self.project,
            budget_year=2026,
            status=S.APPROVED,
            approved_by="Board",
            approved_date=datetime.date(2026, 10, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            older.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

    def test_submitting_fills_submitted_date(self):
        budget = Budget(project=self.project, budget_year=2027, status=S.SUBMITTED)
        budget.full_clean()
        self.assertIsNotNone(budget.submitted_date)

    def test_totals_and_fiscal_year_span(self):
        budget = make_budget(self.project)
        add_line(budget, BudgetLineItem.Category.DESIGN, {2027: "100000"})
        add_line(budget, BudgetLineItem.Category.CONSTRUCTION, {2028: "900000", 2029: "500000.50"})
        self.assertEqual(budget.total, Decimal("1500000.50"))
        self.assertEqual(budget.fiscal_years, "FY2027–FY2029")
        self.assertEqual(make_budget(self.project, 2028).fiscal_years, "")

    def test_line_items_locked_once_approved(self):
        budget = make_budget(self.project, 2027, S.APPROVED)
        with self.assertRaises(ValidationError):
            BudgetLineItem(budget=budget, category=BudgetLineItem.Category.DESIGN).full_clean()
        item = add_line(budget)
        with self.assertRaises(ValidationError):
            BudgetAmount(line_item=item, fiscal_year=2027, amount=1).full_clean()

    def test_one_amount_per_line_item_year(self):
        item = add_line(make_budget(self.project), amounts={2027: "1"})
        with self.assertRaises(ValidationError):
            BudgetAmount(line_item=item, fiscal_year=2027, amount=2).full_clean()

    def test_copy_makes_new_draft_with_same_amounts(self):
        source = make_budget(self.project, 2027, S.APPROVED)
        add_line(source, BudgetLineItem.Category.LAND, {2027: "50000", 2028: "25000"}, "Easements")
        copy = source.copy(2028)
        self.assertEqual((copy.budget_year, copy.status), (2028, S.DRAFT))
        self.assertEqual(copy.total, Decimal("75000"))
        self.assertEqual(copy.line_items.get().description, "Easements")
        self.assertEqual(source.line_items.count(), 1)

    def test_deleting_project_deletes_budgets(self):
        add_line(make_budget(self.project), amounts={2027: "1"})
        self.project.delete()
        self.assertFalse(BudgetAmount.objects.exists())
