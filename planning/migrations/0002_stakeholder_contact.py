"""
Move stakeholder identity onto shared pm contacts.

Each stakeholder's free-text name / organization / contact details become a
``pm.Contact``; stakeholders with the same name and organization share one
contact (unless they're on the same project, where they'd break the new
one-entry-per-contact rule, so they get separate contacts). Contacts are created
as External; mark utility staff Internal afterwards. The reverse copies the
contact's details back onto the stakeholder and leaves the contacts in place.
"""
import django.db.models.deletion
from django.db import migrations, models


def split_contact_details(text):
    """Old free-text ``contact`` -> Contact fields (email, phone or a note)."""
    text = text.strip()
    if not text:
        return {}
    if "@" in text and " " not in text and len(text) <= 254:
        return {"email": text}
    if len(text) <= 40:
        return {"phone": text}
    return {"role_description": f"Contact details: {text}"}


def stakeholders_to_contacts(apps, schema_editor):
    Stakeholder = apps.get_model("planning", "Stakeholder")
    Contact = apps.get_model("pm", "Contact")
    shared = {}  # (name, organization) -> Contact
    used = set()  # (project_id, contact_id)
    for stakeholder in Stakeholder.objects.order_by("created_at", "id"):
        key = (stakeholder.name.strip(), stakeholder.organization.strip())
        details = split_contact_details(stakeholder.contact_details)
        contact = shared.get(key)
        if contact is None or (stakeholder.project_id, contact.pk) in used:
            contact = Contact.objects.create(name=key[0], organization=key[1], contact_type="EXTERNAL", **details)
            shared.setdefault(key, contact)
        else:
            # Fill details the shared contact doesn't have yet.
            changed = [f for f, v in details.items() if f != "role_description" and not getattr(contact, f)]
            for f in changed:
                setattr(contact, f, details[f])
            if changed:
                contact.save(update_fields=changed)
        used.add((stakeholder.project_id, contact.pk))
        stakeholder.contact = contact
        stakeholder.save(update_fields=["contact"])


def contacts_to_stakeholders(apps, schema_editor):
    Stakeholder = apps.get_model("planning", "Stakeholder")
    for stakeholder in Stakeholder.objects.select_related("contact"):
        contact = stakeholder.contact
        stakeholder.name = contact.name
        stakeholder.organization = contact.organization
        stakeholder.contact_details = contact.phone or contact.email
        stakeholder.save(update_fields=["name", "organization", "contact_details"])


class Migration(migrations.Migration):

    dependencies = [
        ("pm", "0003_contact"),
        ("planning", "0001_initial"),
    ]

    operations = [
        # Free the name "contact" for the new foreign key.
        migrations.RenameField(model_name="stakeholder", old_name="contact", new_name="contact_details"),
        migrations.AddField(
            model_name="stakeholder",
            name="contact",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="stakeholder_roles",
                to="pm.contact",
                help_text="Person or group.",
            ),
        ),
        migrations.RunPython(stakeholders_to_contacts, contacts_to_stakeholders),
    ]
