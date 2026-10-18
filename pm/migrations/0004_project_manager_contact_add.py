"""
Project manager as a contact, step 1 of 3: add a nullable foreign key beside the
old free-text name. Split from the data step because PostgreSQL won't alter a
table with pending trigger events in the same transaction.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pm", "0003_contact"),
    ]

    operations = [
        # Free the name "project_manager" for the new foreign key.
        migrations.RenameField(model_name="project", old_name="project_manager", new_name="project_manager_name"),
        # Nullable while both fields exist, so the reverse can re-add the column before filling it.
        migrations.AlterField(
            model_name="project", name="project_manager_name", field=models.CharField(max_length=200, null=True)
        ),
        migrations.AddField(
            model_name="project",
            name="project_manager",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="managed_projects",
                to="pm.contact",
            ),
        ),
    ]
