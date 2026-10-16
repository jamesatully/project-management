"""
Second half of the stakeholder -> contact change (see 0002): drop the old free-text
fields and require a contact. Separate from 0002 because PostgreSQL won't alter
tables in the same transaction as the data conversion.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pm", "0003_contact"),
        ("planning", "0002_stakeholder_contact"),
    ]

    operations = [
        # A default lets the rollback re-add the column before 0002's reverse refills it.
        migrations.AlterField(
            model_name="stakeholder", name="name",
            field=models.CharField(max_length=200, default="", help_text="Person or group."),
        ),
        migrations.RemoveField(model_name="stakeholder", name="name"),
        migrations.RemoveField(model_name="stakeholder", name="organization"),
        migrations.RemoveField(model_name="stakeholder", name="contact_details"),
        migrations.AlterField(
            model_name="stakeholder",
            name="contact",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stakeholder_roles",
                to="pm.contact",
                help_text="Person or group.",
            ),
        ),
        migrations.AlterModelOptions(name="stakeholder", options={"ordering": ["project", "contact__name"]}),
        migrations.AddConstraint(
            model_name="stakeholder",
            constraint=models.UniqueConstraint(
                fields=("project", "contact"),
                name="one_stakeholder_entry_per_contact",
                violation_error_message="This contact is already a stakeholder on this project.",
            ),
        ),
    ]
