"""Tests for the stakeholder -> contact data migration (planning 0002/0003)."""
import importlib

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

migration = importlib.import_module("planning.migrations.0002_stakeholder_contact")

BEFORE = [("pm", "0003_contact"), ("planning", "0001_initial")]
AFTER = [("pm", "0003_contact"), ("planning", "0003_stakeholder_contact_required")]


class SplitContactDetailsTests(SimpleTestCase):
    def test_split(self):
        split = migration.split_contact_details
        self.assertEqual(split(" "), {})
        self.assertEqual(split("robin@agency.example"), {"email": "robin@agency.example"})
        self.assertEqual(split("(503) 555-0150"), {"phone": "(503) 555-0150"})
        self.assertIn("role_description", split("Call the front desk and ask for the permit coordinator on duty"))


class StakeholderToContactMigrationTests(TransactionTestCase):
    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_forward_and_back(self):
        old = self.migrate(BEFORE)
        Project, Stakeholder = old.get_model("pm", "Project"), old.get_model("planning", "Stakeholder")
        p1 = Project.objects.create(name="A", project_id="2021-1-1-0", budget_id="1", project_type="CIP_RR",
                                    project_manager="Pat")
        p2 = Project.objects.create(name="B", project_id="2021-1-2-0", budget_id="1", project_type="CIP_RR",
                                    project_manager="Pat")
        Stakeholder.objects.create(project=p1, name="Robin Lo", organization="State DEQ", contact="(503) 555-0150")
        Stakeholder.objects.create(project=p2, name="Robin Lo", organization="State DEQ", contact="")
        Stakeholder.objects.create(project=p1, name="Robin Lo", organization="State DEQ", contact="robin@deq.example")
        Stakeholder.objects.create(project=p1, name="Board", organization="", role="Approves budget")

        new = self.migrate(AFTER)
        Contact, Stakeholder = new.get_model("pm", "Contact"), new.get_model("planning", "Stakeholder")
        robins = Contact.objects.filter(name="Robin Lo").order_by("created_at")
        # Shared across projects; a second entry on the same project gets its own contact.
        self.assertEqual(robins.count(), 2)
        self.assertEqual(robins[0].phone, "(503) 555-0150")
        self.assertEqual(robins[0].stakeholder_roles.count(), 2)
        self.assertEqual(robins[1].email, "robin@deq.example")
        self.assertEqual(Stakeholder.objects.get(role="Approves budget").contact.name, "Board")
        self.assertEqual(Contact.objects.exclude(contact_type="EXTERNAL").count(), 0)

        old = self.migrate(BEFORE)
        Stakeholder = old.get_model("planning", "Stakeholder")
        rows = sorted(Stakeholder.objects.values_list("name", "organization", "contact"))
        self.assertEqual(rows, sorted([
            ("Board", "", ""), ("Robin Lo", "State DEQ", "(503) 555-0150"), ("Robin Lo", "State DEQ", "(503) 555-0150"),
            ("Robin Lo", "State DEQ", "robin@deq.example"),
        ]))
