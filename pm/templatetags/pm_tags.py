from django import template

from .. import display

register = template.Library()


@register.filter
def money(value):
    """Format a Decimal as $1,234.56."""
    return display.money(value)


@register.filter
def status_badge(obj, field_name="status"):
    """Render ``obj.<field_name>`` as a coloured status badge."""
    return display.status_badge(obj, field_name)


@register.filter
def score_badge(score):
    """Render a 1-25 risk score as a Low/Medium/High badge."""
    return display.score_badge(score)
