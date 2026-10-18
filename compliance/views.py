"""Dashboard panel for permit compliance (registered in compliance/resources.py)."""
import datetime

from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from .models import ComplianceMilestone

UPCOMING_DAYS = 30


def compliance_deadlines_panel(request):
    """Overdue milestones and those due in the next 30 days, soonest first."""
    today = timezone.localdate()
    horizon = today + datetime.timedelta(days=UPCOMING_DAYS)
    open_milestones = ComplianceMilestone.objects.open()
    due = open_milestones.filter(due_date__lte=horizon).select_related("permit", "manager").order_by("due_date", "name")
    list_url = reverse("pm:compliancemilestone-list")
    return {
        "template": "compliance/panel_deadlines.html",
        "milestones": due[:8],
        "overdue_count": open_milestones.filter(due_date__lt=today).count(),
        "upcoming_count": open_milestones.filter(due_date__gte=today, due_date__lte=horizon).count(),
        "upcoming_days": UPCOMING_DAYS,
        "overdue_url": f"{list_url}?{urlencode({'status': ComplianceMilestone.OVERDUE, 'o': 'due_date'})}",
        "all_url": f"{list_url}?{urlencode({'status': 'OPEN', 'o': 'due_date'})}",
    }
