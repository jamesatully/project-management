from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from pm.tests.factories import make_project

from ..models import ActivityNote, ProjectPlan, Risk, previous_month


class PlanningViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="pw-123456!")
        self.client.force_login(self.user)
        self.project = make_project(status="CONSTRUCTION")
        self.plan_url = reverse("planning:project-plan", args=[self.project.pk])
        self.activity_url = reverse("planning:project-activity", args=[self.project.pk])

    def test_project_detail_has_plan_and_activity_tabs(self):
        response = self.client.get(self.project.get_absolute_url())
        self.assertContains(response, self.plan_url)
        self.assertContains(response, self.activity_url)

    def test_plan_tab_without_plan_offers_start(self):
        response = self.client.get(self.plan_url)
        self.assertContains(response, "Start plan")

    def test_plan_tab_shows_plan_and_sections(self):
        ProjectPlan.objects.create(project=self.project, problem_statement="Old pipes break.", scope_out="Paving")
        Risk.objects.create(project=self.project, title="Rock excavation", category="COST", likelihood=3, impact=4)
        response = self.client.get(self.plan_url)
        for text in ["Old pipes break.", "Paving", "Rock excavation", "Risk Register", "Communication Plan"]:
            self.assertContains(response, text)

    def test_add_risk_returns_to_plan_tab(self):
        url = f"{reverse('pm:risk-create')}?project={self.project.pk}&next={self.plan_url}"
        response = self.client.post(url, {
            "project": self.project.pk, "title": "Permit delay", "category": "REGULATORY", "status": "OPEN",
            "likelihood": 3, "impact": 3, "identified_date": "2026-09-01",
        })
        self.assertRedirects(response, self.plan_url)
        self.assertEqual(Risk.objects.get(title="Permit delay").score, 9)

    def test_next_must_be_local(self):
        url = f"{reverse('pm:risk-create')}?next=https://evil.example/"
        response = self.client.post(url, {
            "project": self.project.pk, "title": "X", "category": "COST", "status": "OPEN",
            "likelihood": 1, "impact": 1, "identified_date": "2026-09-01",
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response["Location"])

    def test_monthly_update_form_accepts_month_input(self):
        period = previous_month()
        url = f"{reverse('pm:activitynote-create')}?next={self.activity_url}"
        response = self.client.post(url, {
            "project": self.project.pk, "note_type": "MONTHLY", "period": period.strftime("%Y-%m"),
            "note_date": "2026-10-02", "author_name": "Pat Example", "body": "Work progressed.",
        })
        self.assertRedirects(response, self.activity_url)
        self.assertEqual(ActivityNote.objects.get().period, period)
        self.assertContains(self.client.get(self.activity_url), "monthly update submitted")

    def test_activity_tab_prompts_for_missing_update(self):
        response = self.client.get(self.activity_url)
        self.assertContains(response, "No monthly update yet")

    def test_dashboard_panels(self):
        Risk.objects.create(project=self.project, title="Bypass failure", category="ENVIRONMENTAL", likelihood=5, impact=5)
        response = self.client.get(reverse("pm:dashboard"))
        self.assertContains(response, "Monthly updates due")
        self.assertContains(response, "Bypass failure")
        self.assertContains(response, self.project.name)  # listed as missing an update

    def test_all_planning_pages_render(self):
        plan = ProjectPlan.objects.create(project=self.project)
        risk = Risk.objects.create(project=self.project, title="R", category="COST", likelihood=1, impact=1)
        for name, args in [("plan-list", []), ("risk-list", []), ("milestone-list", []), ("activitynote-list", []),
                           ("objective-list", []), ("stakeholder-list", []), ("communicationitem-list", []),
                           ("plan-update", [plan.pk]), ("risk-detail", [risk.pk]), ("risk-update", [risk.pk])]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"pm:{name}", args=args)).status_code, 200)


class PlanningAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("api", password="pw-123456!"))
        self.project = make_project()

    def test_endpoints_list(self):
        for endpoint in ["plans", "objectives", "risks", "stakeholders", "milestones", "communication-items",
                         "activity-notes"]:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.get(f"/api/{endpoint}/").status_code, 200)

    def test_create_risk_computes_score(self):
        response = self.client.post("/api/risks/", {
            "project": self.project.pk, "title": "Lead time", "category": "PROCUREMENT", "likelihood": 4, "impact": 4,
        })
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["score"], 16)
        self.assertEqual(self.client.get("/api/risks/?score_min=15").data["count"], 1)

    def test_monthly_note_validation(self):
        base = {"project": self.project.pk, "note_type": "MONTHLY", "author_name": "Pat", "body": "x"}
        self.assertEqual(self.client.post("/api/activity-notes/", base).status_code, 400)  # no period
        response = self.client.post("/api/activity-notes/", {**base, "period": "2026-09-15"})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["period"], "2026-09-01")
        self.assertEqual(self.client.post("/api/activity-notes/", {**base, "period": "2026-09-01"}).status_code, 400)
