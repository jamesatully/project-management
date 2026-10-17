from decimal import Decimal

from django.test import TestCase

from pm.models import Project
from pm.tests.factories import make_project

from .. import rollup
from ..models import Budget, BudgetLineItem
from .factories import add_line, make_budget

S, C = Budget.Status, BudgetLineItem.Category


class ProgramBudgetTests(TestCase):
    def setUp(self):
        # R&R project: adopted FY2027 budget, superseding FY2026, with an FY2028 draft in progress.
        self.rr = make_project(project_id="2024-1-1-0")
        add_line(make_budget(self.rr, 2026, S.APPROVED), C.CONSTRUCTION, {2026: "100", 2027: "100"})
        add_line(make_budget(self.rr, 2027, S.APPROVED), C.CONSTRUCTION, {2026: "100", 2027: "200", 2032: "50"})
        draft = make_budget(self.rr, 2028)
        add_line(draft, C.CONSTRUCTION, {2028: "300"})
        add_line(draft, C.DESIGN, {2028: "40"})
        # Expansion project only approved for FY2026 (not updated since): it carries forward.
        self.exp = make_project(project_id="2025-1-1-0", project_type=Project.ProjectType.CIP_EXPANSION)
        add_line(make_budget(self.exp, 2026, S.APPROVED), C.LAND, {2027: "70", 2028: "80"})
        # Cancelled projects are left out.
        gone = make_project(project_id="2025-2-2-0", status=Project.Status.CANCELLED)
        add_line(make_budget(gone, 2027, S.APPROVED), C.DESIGN, {2027: "999"})
        # Rejected versions never count.
        add_line(make_budget(make_project(project_id="2025-3-3-0"), 2028, S.REJECTED), C.DESIGN, {2028: "5"})

    def programs(self, report):
        return {p["key"]: p for p in report["programs"]}

    def test_adopted_uses_latest_approved_budget(self):
        report = rollup.program_budget(2027, "adopted")
        self.assertEqual(report["years"], [2027, 2028, 2029, 2030, 2031])
        rr = self.programs(report)["CIP_RR"]
        self.assertEqual(len(rr["projects"]), 1)
        row = rr["totals"]
        self.assertEqual(
            (row.prior, row.first_year, row.plan_total, row.later, row.total),
            (Decimal(100), Decimal(200), Decimal(200), Decimal(50), Decimal(350)),
        )
        self.assertEqual(self.programs(report)["CIP_EXPANSION"]["totals"].plan_total, Decimal(150))
        self.assertEqual(report["totals"].plan_total, Decimal(350))

    def test_proposed_includes_drafts_and_carries_others_forward(self):
        report = rollup.program_budget(2028, "proposed")
        rr = self.programs(report)["CIP_RR"]
        self.assertEqual(rr["projects"][0]["budget"].budget_year, 2028)
        self.assertEqual(rr["totals"].first_year, Decimal(340))
        categories = {c["key"]: c["row"].total for c in rr["categories"]}
        self.assertEqual((categories["CONSTRUCTION"], categories["DESIGN"]), (Decimal(300), Decimal(40)))
        # The expansion project has no FY2028 version; its FY2026 budget carries forward.
        self.assertEqual(self.programs(report)["CIP_EXPANSION"]["totals"].first_year, Decimal(80))

    def test_earlier_cycle_uses_budgets_approved_then(self):
        report = rollup.program_budget(2026, "adopted")
        self.assertEqual(self.programs(report)["CIP_RR"]["projects"][0]["budget"].budget_year, 2026)

    def test_program_filter_and_projects_with_nothing_remaining(self):
        report = rollup.program_budget(2027, "adopted", program="CIP_EXPANSION")
        self.assertEqual(list(self.programs(report)), ["CIP_EXPANSION"])
        # By FY2029 the expansion project has nothing left, so it drops out.
        self.assertNotIn("CIP_EXPANSION", self.programs(rollup.program_budget(2029, "adopted")))
