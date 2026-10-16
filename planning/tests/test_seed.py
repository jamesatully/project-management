from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from django.db.models import Count

from pm.models import Contact, Project

from ..models import ActivityNote, Milestone, ProjectPlan, Risk, Stakeholder


class PlanningSeedTests(TestCase):
    def test_seed_demo_includes_planning_data(self):
        call_command("seed_demo", "--projects", "15", "--today", "2026-06-30", stdout=StringIO())
        self.assertTrue(ProjectPlan.objects.exists())
        self.assertTrue(Risk.objects.exists())
        self.assertTrue(Milestone.objects.filter(status="COMPLETE", actual_date__isnull=False).exists())
        # Every plan belongs to a seeded project, and monthly notes are on the 1st of the month.
        self.assertEqual(ProjectPlan.objects.exclude(project__in=Project.objects.all()).count(), 0)
        self.assertFalse(ActivityNote.objects.filter(note_type="MONTHLY", period__day__gt=1).exists())
        for risk in Risk.objects.all()[:50]:
            self.assertEqual(risk.score, risk.likelihood * risk.impact)

    def test_stakeholders_reuse_directory_contacts(self):
        call_command("seed_demo", "--projects", "15", "--today", "2026-06-30", stdout=StringIO())
        self.assertTrue(Stakeholder.objects.exists())
        # Recurring people (sponsor, budget analyst, ...) are one contact across projects.
        self.assertLess(Contact.objects.filter(stakeholder_roles__isnull=False).distinct().count(),
                        Stakeholder.objects.count())
        self.assertTrue(Contact.objects.annotate(n=Count("stakeholder_roles")).filter(n__gt=1).exists())
        self.assertTrue(Stakeholder.objects.filter(contact__contact_type="INTERNAL").exists())
        self.assertTrue(Stakeholder.objects.filter(contact__contact_type="EXTERNAL").exists())
