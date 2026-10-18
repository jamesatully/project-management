"""Compliance REST API. Same conventions as pm.api: filters, ?search=, ?ordering=, pagination."""
from rest_framework import viewsets

from .. import filters
from ..models import ComplianceMilestone, Permit
from . import serializers


class PermitViewSet(viewsets.ModelViewSet):
    queryset = Permit.objects.select_related("compliance_unit")
    serializer_class = serializers.PermitSerializer
    filterset_class = filters.PermitFilter
    search_fields = ["name", "permit_number", "issuing_agency", "description", "compliance_unit__name"]
    ordering_fields = ["name", "permit_number", "status", "effective_date", "expiration_date"]


class ComplianceMilestoneViewSet(viewsets.ModelViewSet):
    queryset = ComplianceMilestone.objects.select_related("permit", "manager", "submittal_document")
    serializer_class = serializers.ComplianceMilestoneSerializer
    filterset_class = filters.ComplianceMilestoneFilter
    search_fields = ["name", "permit_condition", "description", "permit__name", "permit__permit_number", "manager__name"]
    ordering_fields = ["name", "due_date", "target_date", "submitted_date", "status", "permit_condition"]
