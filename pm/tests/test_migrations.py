"""Tests for the project manager name -> contact data migration (pm 0004-0006)."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("pm", "0003_contact")]
AFTER = [("pm", "0006_project_manager_contact_required")]


class ProjectManagerToContactMigrationTests(TransactionTestCase):
    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_forward_and_back(self):
        old = self.migrate(BEFORE)
        Project, Contact = old.get_model("pm", "Project"), old.get_model("pm", "Contact")
        Contact.objects.create(name="Dana Lee", title="Inspector", contact_type="INTERNAL")
        dana = Contact.objects.create(name="Dana Lee", title="Senior Project Manager", contact_type="INTERNAL")
        Contact.objects.create(name="Sam Roe", organization="Acme Engineering", contact_type="EXTERNAL")
        projects = {}
        for i, name in enumerate(["Dana Lee", "dana  lee", "Sam Roe", "Sam Roe"], start=1):
            projects[i] = Project.objects.create(
                name=f"P{i}", project_id=f"2021-1-{i}-0", budget_id="1", project_type="CIP_RR", project_manager=name
            ).pk

        new = self.migrate(AFTER)
        Project, Contact = new.get_model("pm", "Project"), new.get_model("pm", "Contact")
        manager = {pk: Project.objects.get(pk=pk).project_manager for pk in projects.values()}
        # Matched to the internal contact titled project manager, ignoring case and spacing.
        self.assertEqual(manager[projects[1]].pk, dana.pk)
        self.assertEqual(manager[projects[2]].pk, dana.pk)
        # An external contact with the same name isn't used; one internal contact is created and shared.
        sam = manager[projects[3]]
        self.assertEqual((sam.name, sam.contact_type, sam.title), ("Sam Roe", "INTERNAL", "Project Manager"))
        self.assertEqual(manager[projects[4]].pk, sam.pk)
        self.assertEqual(Contact.objects.count(), 4)

        old = self.migrate(BEFORE)
        Project = old.get_model("pm", "Project")
        self.assertEqual(
            sorted(Project.objects.values_list("project_manager", flat=True)),
            ["Dana Lee", "Dana Lee", "Sam Roe", "Sam Roe"],
        )
