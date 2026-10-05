import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase

from pm.tests.factories import make_project

from ..models import ActivityNote, Milestone, ProjectPlan, Risk, Stakeholder, previous_month


class PlanningModelTests(TestCase):
    def setUp(self):
        self.project = make_project()

    def test_risk_score_is_likelihood_times_impact(self):
        risk = Risk.objects.create(project=self.project, title="Rock", category="COST", likelihood=4, impact=3)
        self.assertEqual(risk.score, 12)
        risk.impact = 5
        risk.save()
        self.assertEqual(risk.score, 20)

    def test_approved_plan_needs_approver_and_date(self):
        plan = ProjectPlan(project=self.project, status=ProjectPlan.Status.APPROVED)
        with self.assertRaises(ValidationError):
            plan.full_clean()
        plan.approved_by, plan.approved_date = "Renee Castellano", datetime.date(2026, 1, 5)
        plan.full_clean()

    def test_completed_milestone_needs_actual_date(self):
        m = Milestone(project=self.project, name="NTP", planned_date=datetime.date(2026, 3, 1), status="COMPLETE")
        with self.assertRaises(ValidationError):
            m.full_clean()

    def test_milestone_variance(self):
        m = Milestone(project=self.project, name="NTP", planned_date=datetime.date(2026, 3, 1),
                      forecast_date=datetime.date(2026, 3, 11))
        self.assertEqual(m.variance_days, 10)
        m.actual_date = datetime.date(2026, 2, 27)
        self.assertEqual(m.variance_days, -2)

    def test_stakeholder_engagement_strategy(self):
        s = Stakeholder(project=self.project, name="Board", influence="HIGH", interest="LOW")
        self.assertEqual(s.engagement_strategy, "Keep satisfied")

    def test_monthly_note_period_normalized_and_unique(self):
        note = ActivityNote(project=self.project, period=datetime.date(2026, 9, 17), author_name="Dana", body="x")
        note.full_clean()
        self.assertEqual(note.period, datetime.date(2026, 9, 1))
        note.save()
        dup = ActivityNote(project=self.project, period=datetime.date(2026, 9, 2), author_name="Dana", body="y")
        with self.assertRaises(ValidationError):
            dup.full_clean()
        # Other note types may share the month.
        ActivityNote(project=self.project, note_type="ISSUE", period=datetime.date(2026, 9, 1),
                     author_name="Dana", body="z").full_clean()

    def test_monthly_note_requires_period(self):
        with self.assertRaises(ValidationError):
            ActivityNote(project=self.project, author_name="Dana", body="x").full_clean()

    def test_previous_month(self):
        self.assertEqual(previous_month(datetime.date(2026, 1, 15)), datetime.date(2025, 12, 1))
