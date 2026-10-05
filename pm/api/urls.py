from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet)
router.register("vendors", views.VendorViewSet)
router.register("compliance-units", views.ComplianceUnitViewSet)
router.register("purchase-orders", views.PurchaseOrderViewSet)
router.register("invoices", views.InvoiceViewSet)
router.register("field-reports", views.FieldReportViewSet)
router.register("documents", views.DocumentViewSet)

urlpatterns = router.urls
