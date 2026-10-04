"""
Load the fictitious water/wastewater utility demo dataset.

    python manage.py seed_demo            # into empty pm tables
    python manage.py seed_demo --flush    # replace existing pm data
    python manage.py seed_demo --seed 7   # a different (still reproducible) dataset
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pm import demo
from pm.models import Document, FieldReport, Invoice, Project, PurchaseOrder, Vendor

# Delete order respects PROTECT foreign keys.
MODELS = [Invoice, FieldReport, Document, PurchaseOrder, Project, Vendor]


class Command(BaseCommand):
    help = "Populate the database with fictitious water/wastewater utility demo data."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete all existing pm data first.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42).")
        parser.add_argument("--projects", type=int, default=100, help="Approximate number of projects (default 100).")
        parser.add_argument(
            "--today", type=datetime.date.fromisoformat, default=None,
            help="Reference date (YYYY-MM-DD) for statuses and history; defaults to today.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        existing = sum(m.objects.count() for m in MODELS)
        if existing and not options["flush"]:
            raise CommandError(f"{existing} pm records already exist. Re-run with --flush to replace them.")
        if options["flush"]:
            for model in MODELS:
                model.objects.all().delete()

        counts = demo.generate(seed=options["seed"], today=options["today"], project_count=options["projects"])
        for label, n in counts.items():
            self.stdout.write(f"  {label:<16} {n:>6}")
        self.stdout.write(self.style.SUCCESS("Demo data loaded."))
