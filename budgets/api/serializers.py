from django.db import transaction
from rest_framework import serializers

from pm.api.serializers import ModelCleanMixin

from ..models import Budget, BudgetAmount, BudgetLineItem

AUDIT = ["created_at", "updated_at"]


class BudgetAmountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetAmount
        fields = ["fiscal_year", "amount"]


class BudgetLineItemSerializer(ModelCleanMixin, serializers.ModelSerializer):
    """A line item with its fiscal-year amounts. Writing ``amounts`` replaces the whole list."""

    category_display = serializers.CharField(source="get_category_display", read_only=True)
    amounts = BudgetAmountSerializer(many=True, required=False)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BudgetLineItem
        fields = ["id", "budget", "category", "category_display", "description", "amounts", "total", *AUDIT]

    def validate(self, attrs):
        amounts = attrs.pop("amounts", None)  # a reverse relation can't be set on the instance ModelCleanMixin checks
        if self.instance and "budget" in attrs and attrs["budget"] != self.instance.budget:
            raise serializers.ValidationError({"budget": "A line item can't move to another budget."})
        attrs = super().validate(attrs)
        if amounts is not None:
            years = [a["fiscal_year"] for a in amounts]
            if len(years) != len(set(years)):
                raise serializers.ValidationError({"amounts": "Each fiscal year can appear only once."})
            attrs["amounts"] = amounts
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        amounts = validated_data.pop("amounts", [])
        item = super().create(validated_data)
        self.write_amounts(item, amounts)
        return item

    @transaction.atomic
    def update(self, instance, validated_data):
        amounts = validated_data.pop("amounts", None)
        item = super().update(instance, validated_data)
        if amounts is not None:
            item.amounts.all().delete()
            self.write_amounts(item, amounts)
        return item

    def write_amounts(self, item, amounts):
        BudgetAmount.objects.bulk_create([BudgetAmount(line_item=item, **a) for a in amounts if a["amount"]])


class BudgetSerializer(ModelCleanMixin, serializers.ModelSerializer):
    project_display = serializers.CharField(source="project", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    line_items = BudgetLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Budget
        fields = [
            "id",
            "project",
            "project_display",
            "budget_year",
            "status",
            "status_display",
            "prepared_by",
            "submitted_date",
            "approved_by",
            "approved_date",
            "superseded_by",
            "notes",
            "total",
            "line_items",
            *AUDIT,
        ]
        read_only_fields = ["superseded_by"]
