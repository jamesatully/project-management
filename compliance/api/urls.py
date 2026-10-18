from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("permits", views.PermitViewSet)
router.register("compliance-milestones", views.ComplianceMilestoneViewSet)

urlpatterns = router.urls
