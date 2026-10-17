import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from pm.tests.factories import make_project

from ..models import Budget, BudgetLineItem
from .factories import add_line, make_budget

S = Budget.Status


class BudgetApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("api", password="pw-123456!"))
        self.project = make_project()

    def test_create_line_item_with_amounts_and_read_budget(self):
        budget = make_budget(self.project, 2028)
        response = self.client.post(
            "/api/budget-line-items/",
            {
                "budget": str(budget.pk),
                "category": "CONSTRUCTION",
                "description": "Contract",
                "amounts": [{"fiscal_year": 2028, "amount": "600000.00"}, {"fiscal_year": 2029, "amount": "400000.00"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "1000000.00")
        data = self.client.get(f"/api/budgets/{budget.pk}/").data
        self.assertEqual(data["total"], "1000000.00")
        self.assertEqual(len(data["line_items"][0]["amounts"]), 2)

    def test_update_replaces_amounts(self):
        item = add_line(make_budget(self.project, 2028), amounts={2028: "1", 2029: "2"})
        response = self.client.patch(
            f"/api/budget-line-items/{item.pk}/", {"amounts": [{"fiscal_year": 2030, "amount": "5"}]}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(list(item.amounts.values_list("fiscal_year", flat=True)), [2030])

    def test_duplicate_years_rejected(self):
        budget = make_budget(self.project, 2028)
        response = self.client.post(
            "/api/budget-line-items/",
            {
                "budget": str(budget.pk),
                "category": "DESIGN",
                "amounts": [{"fiscal_year": 2028, "amount": "1"}, {"fiscal_year": 2028, "amount": "2"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("amounts", response.data)

    def test_locked_budget_rejects_line_item_changes(self):
        budget = make_budget(self.project, 2027, S.APPROVED)
        item = add_line(budget)
        response = self.client.post(
            "/api/budget-line-items/", {"budget": str(budget.pk), "category": "DESIGN"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete(f"/api/budget-line-items/{item.pk}/").status_code, 400)
        self.assertTrue(BudgetLineItem.objects.filter(pk=item.pk).exists())

    def test_approve_via_api_supersedes_and_validates(self):
        old = make_budget(self.project, 2027, S.APPROVED)
        new = make_budget(self.project, 2028)
        response = self.client.patch(f"/api/budgets/{new.pk}/", {"status": "APPROVED"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("approved_date", response.data)
        response = self.client.patch(
            f"/api/budgets/{new.pk}/",
            {"status": "APPROVED", "approved_by": "Board", "approved_date": "2027-09-15"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        old.refresh_from_db()
        self.assertEqual((old.status, old.superseded_by_id), (S.SUPERSEDED, new.pk))

    def test_duplicate_cycle_rejected(self):
        make_budget(self.project, 2028)
        response = self.client.post(
            "/api/budgets/", {"project": str(self.project.pk), "budget_year": 2028}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_filters(self):
        make_budget(self.project, 2027, S.APPROVED)
        make_budget(self.project, 2028)
        self.assertEqual(self.client.get("/api/budgets/", {"budget_year": 2028}).data["count"], 1)
        self.assertEqual(
            self.client.get("/api/budgets/", {"status": "APPROVED", "project_type": "CIP_RR"}).data["count"], 1
        )

    def test_program_budget_endpoint(self):
        budget = make_budget(self.project, 2027, S.APPROVED, approved_date=datetime.date(2026, 9, 15))
        add_line(budget, BudgetLineItem.Category.DESIGN, {2027: "100", 2033: "5"})
        data = self.client.get("/api/program-budget/", {"cycle": 2027}).data
        self.assertEqual(data["fiscal_years"], ["FY2027", "FY2028", "FY2029", "FY2030", "FY2031"])
        program = data["programs"][0]
        self.assertEqual(program["program"], "CIP_RR")
        self.assertEqual(program["totals"]["fiscal_years"]["FY2027"], "100.00")
        self.assertEqual(program["totals"]["later_years"], "5.00")
        self.assertEqual(program["projects"][0]["project_id"], self.project.project_id)
        self.assertEqual(data["totals"]["total"], "105.00")
        self.assertEqual(self.client.get("/api/program-budget/", {"basis": "nope"}).status_code, 400)
