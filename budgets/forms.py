"""
Budget forms. :class:`BudgetForm` edits a version's details through pm's generic
form pages; :func:`line_item_formset` builds the spreadsheet-style editor where
each row is a line item and each fiscal year is a column.
"""

from django import forms
from django.db import transaction

from pm.forms import INPUT_CLASSES, StyledModelForm

from .models import Budget, BudgetAmount, BudgetLineItem


class BudgetForm(StyledModelForm):
    class Meta:
        model = Budget
        fields = [
            "project",
            "budget_year",
            "status",
            "prepared_by",
            "submitted_date",
            "approved_by",
            "approved_date",
            "notes",
        ]
        help_texts = {"status": "Approving a budget supersedes the project's previously approved budget."}


def year_field(name):
    return f"fy{name}"


class LineItemRowForm(forms.ModelForm):
    """A line item plus one amount field per fiscal year (``fy2027``, ...)."""

    class Meta:
        model = BudgetLineItem
        fields = ["category", "description"]

    def __init__(self, *args, years=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.years = list(years)
        existing = {a.fiscal_year: a.amount for a in self.instance.amounts.all()} if self.instance.pk else {}
        # Show whole-dollar amounts without ".00".
        existing = {fy: int(v) if v == v.to_integral_value() else v for fy, v in existing.items()}
        for fy in self.years:
            self.fields[year_field(fy)] = forms.DecimalField(
                label=f"FY{fy}",
                required=False,
                min_value=0,
                max_digits=14,
                decimal_places=2,
                initial=existing.get(fy),
                widget=forms.NumberInput(attrs={"step": "1", "inputmode": "decimal", "data-fy": fy}),
            )
        # Fixed widths (not INPUT_CLASSES' w-full) so several years fit across the card.
        compact = INPUT_CLASSES.replace("w-full ", "").replace("px-4", "px-3")
        self.fields["category"].widget.attrs["class"] = compact + " w-48"
        self.fields["description"].widget.attrs = {"class": compact + " w-36", "placeholder": "Optional detail"}
        for fy in self.years:
            self.fields[year_field(fy)].widget.attrs["class"] = compact + " w-[7.5rem] text-right tabular-nums"

    def amount_fields(self):
        return [self[year_field(fy)] for fy in self.years]

    def save_amounts(self):
        """Write the year fields: blank or zero removes that year's amount."""
        item = self.instance
        current = {a.fiscal_year: a for a in item.amounts.all()}
        for fy in self.years:
            value = self.cleaned_data.get(year_field(fy))
            amount = current.get(fy)
            if not value:
                if amount:
                    amount.delete()
            elif amount:
                if amount.amount != value:
                    amount.amount = value
                    amount.save(update_fields=["amount", "updated_at"])
            else:
                BudgetAmount.objects.create(line_item=item, fiscal_year=fy, amount=value)


class BaseLineItemFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, budget, **kwargs):
        self.budget = budget
        super().__init__(*args, queryset=budget.line_items.prefetch_related("amounts"), **kwargs)

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        form.instance.budget = self.budget  # model clean() checks the budget is still editable
        return form

    def save_all(self):
        with transaction.atomic():
            for form in self.forms:
                if not form.has_changed() and not form.instance.pk:
                    continue
                if self.can_delete and self._should_delete_form(form):
                    if form.instance.pk:
                        form.instance.delete()
                    continue
                if form.has_changed():
                    form.save()
                    form.save_amounts()


def line_item_formset(budget, years, data=None, extra=2):
    FormSet = forms.modelformset_factory(
        BudgetLineItem, form=LineItemRowForm, formset=BaseLineItemFormSet, extra=extra, can_delete=True
    )
    return FormSet(data, budget=budget, form_kwargs={"years": years}, prefix="lines")
