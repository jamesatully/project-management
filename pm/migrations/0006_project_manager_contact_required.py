"""Project manager as a contact, step 3 of 3: require the link and drop the old name."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pm", "0005_project_manager_contact_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="project_manager",
            field=models.ForeignKey(
                help_text="Utility staff member managing the project (an internal contact).",
                limit_choices_to={"contact_type": "INTERNAL"},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="managed_projects",
                to="pm.contact",
            ),
        ),
        migrations.RemoveField(model_name="project", name="project_manager_name"),
    ]
