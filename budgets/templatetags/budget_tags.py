from django import template

from pm import display

register = template.Library()


@register.filter
def amount(value):
    """Money for budget tables: a dash for zero or blank so the figures stand out."""
    return display.money(value) if value else display.EMPTY


@register.filter
def whole_amount(value):
    """Whole dollars for roll-up reports, with a dash for zero."""
    return display.money(value, cents=False) if value else display.EMPTY


@register.filter
def signed_money(value):
    """A change in money, e.g. "+$1,200.00" or "−$500.00"."""
    if value is None:
        return display.EMPTY
    return f"{'−' if value < 0 else '+'}{display.money(abs(value))}"
