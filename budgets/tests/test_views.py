import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from pm.tests.factories import make_project

from ..models import Budget, BudgetLineItem
from .factories import add_line, make_budget

S, C = Budget.Status, BudgetLineItem.Category
TODAY = datetime.date(2026, 10, 16)  # FY2027; the FY2028 budget is being prepared


def management(total, initial):
    return {
        "lines-TOTAL_FORMS": total,
        "lines-INITIAL_FORMS": initial,
        "lines-MIN_NUM_FORMS": 0,
        "lines-MAX_NUM_FORMS": 1000,
    }


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class BudgetViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_login(self.user)
        self.project = make_project(status="DESIGN")
        self.tab_url = reverse("budgets:project-budget", args=[self.project.pk])

    def test_project_has_budget_tab_and_empty_state(self, _today):
        self.assertContains(self.client.get(self.project.get_absolute_url()), self.tab_url)
        response = self.client.get(self.tab_url)
        self.assertContains(response, "Start budget")
        self.assertContains(response, f"{reverse('pm:budget-create')}?project={self.project.pk}")

    def test_tab_shows_approved_version_grid_and_history(self, _today):
        old = make_budget(self.project, 2026, S.APPROVED)
        add_line(old, C.DESIGN, {2026: "100000"})
        current = make_budget(self.project, 2027, S.APPROVED)
        add_line(current, C.DESIGN, {2026: "100000"}, "Engineering design")
        add_line(current, C.CONSTRUCTION, {2027: "750000", 2028: "250000"})
        response = self.client.get(self.tab_url)
        self.assertEqual(response.context["selected"], current)
        for text in [
            "FY2027 Budget",
            "FY2026 Budget",
            "Engineering design",
            "$1,100,000.00",
            "+$1,000,000.00",
            "Superseded",
            "New FY2028 version",
        ]:
            self.assertContains(response, text)
        self.assertNotContains(response, "Edit line items")  # approved budgets are locked
        old_view = self.client.get(f"{self.tab_url}?version={Budget.objects.get(budget_year=2026).pk}")
        self.assertEqual(old_view.context["selected"].budget_year, 2026)
        self.assertContains(old_view, "Superseded by the")

    def test_new_version_copies_budget_into_next_cycle(self, _today):
        source = make_budget(self.project, 2027, S.APPROVED)
        add_line(source, C.CONSTRUCTION, {2027: "500000"})
        response = self.client.post(reverse("budgets:copy", args=[source.pk]))
        new = Budget.objects.get(project=self.project, budget_year=2028)
        self.assertRedirects(response, reverse("budgets:line-items", args=[new.pk]))
        self.assertEqual(
            (new.status, new.total, new.prepared_by), (S.DRAFT, Decimal("500000"), self.project.project_manager.name)
        )
        # Only one version per cycle.
        self.client.post(reverse("budgets:copy", args=[source.pk]))
        self.assertEqual(self.project.budgets.count(), 2)

    def test_line_item_editor_saves_amounts(self, _today):
        budget = make_budget(self.project, 2028)
        url = reverse("budgets:line-items", args=[budget.pk])
        response = self.client.get(url)
        self.assertEqual(response.context["years"], [2028, 2029, 2030, 2031, 2032])
        data = {
            **management(2, 0),
            "fy_from": 2028,
            "fy_to": 2032,
            "lines-0-category": "DESIGN",
            "lines-0-description": "Consultant",
            "lines-0-fy2028": "120000",
            "lines-1-category": "",
            "lines-1-description": "",
        }
        self.assertRedirects(self.client.post(url, data), budget.get_absolute_url())
        item = budget.line_items.get()
        self.assertEqual([(a.fiscal_year, a.amount) for a in item.amounts.all()], [(2028, Decimal("120000.00"))])

        # Edit: change one year, clear another, add a year before the cycle.
        amount = item.amounts.get()
        data = {
            **management(1, 1),
            "fy_from": 2027,
            "fy_to": 2032,
            "lines-0-id": item.pk,
            "lines-0-category": "DESIGN",
            "lines-0-description": "Consultant",
            "lines-0-fy2027": "5000",
            "lines-0-fy2028": "",
            "lines-0-fy2029": "80000",
        }
        self.client.post(url, data)
        self.assertEqual(
            dict(item.amounts.values_list("fiscal_year", "amount")), {2027: Decimal("5000"), 2029: Decimal("80000")}
        )
        self.assertFalse(type(amount).objects.filter(pk=amount.pk).exists())

    def test_line_item_editor_remove_and_validation(self, _today):
        budget = make_budget(self.project, 2028)
        item = add_line(budget, C.LAND, {2028: "10"})
        url = reverse("budgets:line-items", args=[budget.pk])
        bad = {**management(1, 1), "lines-0-id": item.pk, "lines-0-category": "LAND", "lines-0-fy2028": "-5"}
        response = self.client.post(url, bad)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct")
        self.client.post(
            url,
            {
                **management(1, 1),
                "lines-0-id": item.pk,
                "lines-0-category": "LAND",
                "lines-0-fy2028": "10",
                "lines-0-DELETE": "on",
            },
        )
        self.assertFalse(budget.line_items.exists())

    def test_add_year_and_row_redraw_without_saving(self, _today):
        budget = make_budget(self.project, 2028)
        url = reverse("budgets:line-items", args=[budget.pk])
        data = {**management(1, 0), "fy_from": 2028, "fy_to": 2032, "lines-0-category": "DESIGN", "lines-0-fy2028": "7"}
        response = self.client.post(url, {**data, "add_year": "after"})
        self.assertEqual(response.context["years"][-1], 2033)
        self.assertContains(response, 'value="7"')
        response = self.client.post(url, {**data, "add_row": "1"})
        self.assertEqual(len(response.context["formset"].forms), 2)
        self.assertFalse(budget.line_items.exists())

    def test_locked_budget_editor_redirects(self, _today):
        budget = make_budget(self.project, 2027, S.APPROVED)
        response = self.client.get(reverse("budgets:line-items", args=[budget.pk]))
        self.assertRedirects(response, budget.get_absolute_url(), fetch_redirect_response=False)

    def test_approving_through_generic_form_supersedes(self, _today):
        make_budget(self.project, 2027, S.APPROVED)
        draft = make_budget(self.project, 2028)
        response = self.client.post(
            reverse("pm:budget-update", args=[draft.pk]),
            {
                "project": self.project.pk,
                "budget_year": 2028,
                "status": "APPROVED",
                "approved_by": "Board of Commissioners",
                "approved_date": "2027-09-15",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Budget.objects.get(budget_year=2027).status, S.SUPERSEDED)

    def test_budget_list_and_filters(self, _today):
        add_line(make_budget(self.project, 2028), C.DESIGN, {2028: "1234"})
        response = self.client.get(reverse("pm:budget-list"), {"budget_year": 2028, "project_type": "CIP_RR"})
        self.assertContains(response, "FY2028 Budget")
        self.assertContains(response, "$1,234.00")

    def test_program_page(self, _today):
        add_line(make_budget(self.project, 2027, S.APPROVED), C.CONSTRUCTION, {2027: "400000", 2029: "100000"})
        response = self.client.get(reverse("budgets:program"))
        self.assertEqual(response.context["cycle"], 2027)
        for text in ["FY2027 Adopted Capital Program", "CIP R&amp;R", "$500,000<", self.project.name]:
            self.assertContains(response, text)
        response = self.client.get(
            reverse("budgets:program"), {"cycle": 2028, "basis": "proposed", "program": "CIP_EXPANSION"}
        )
        self.assertContains(response, "Nothing budgeted")

    def test_sidebar_and_dashboard_panel(self, _today):
        make_budget(self.project, 2028)
        response = self.client.get(reverse("pm:dashboard"))
        self.assertContains(response, reverse("budgets:program"))
        self.assertContains(response, "FY2028 budget cycle")
        self.assertContains(response, "FY2027 adopted capital program")
