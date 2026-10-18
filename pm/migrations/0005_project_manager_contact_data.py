"""
Project manager as a contact, step 2 of 3: link each project to a contact.

Each distinct name is matched (case-insensitively, ignoring extra spaces) to an
existing Internal contact, preferring one whose job title mentions "project
manager". Names with no match get a new Internal contact titled "Project
Manager". The reverse copies the contact's name back and leaves the contacts in
place.
"""
from django.db import migrations


def match_contact(Contact, name):
    """The Internal contact for a PM name, created if there isn't one."""
    candidates = Contact.objects.filter(name__iexact=name, contact_type="INTERNAL").order_by("created_at", "id")
    for contact in candidates:
        if "project manager" in contact.title.lower():
            return contact
    return candidates.first() or Contact.objects.create(name=name, title="Project Manager", contact_type="INTERNAL")


def names_to_contacts(apps, schema_editor):
    Project = apps.get_model("pm", "Project")
    Contact = apps.get_model("pm", "Contact")
    contacts = {}  # normalised name -> Contact
    for project in Project.objects.order_by("created_at", "id"):
        name = " ".join((project.project_manager_name or "").split()) or "Unassigned"
        key = name.lower()
        if key not in contacts:
            contacts[key] = match_contact(Contact, name)
        project.project_manager = contacts[key]
        project.save(update_fields=["project_manager"])


def contacts_to_names(apps, schema_editor):
    Project = apps.get_model("pm", "Project")
    for project in Project.objects.select_related("project_manager"):
        project.project_manager_name = project.project_manager.name if project.project_manager_id else ""
        project.save(update_fields=["project_manager_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("pm", "0004_project_manager_contact_add"),
    ]

    operations = [
        migrations.RunPython(names_to_contacts, contacts_to_names),
    ]
