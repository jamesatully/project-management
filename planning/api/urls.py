from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("plans", views.ProjectPlanViewSet)
router.register("objectives", views.ObjectiveViewSet)
router.register("risks", views.RiskViewSet)
router.register("stakeholders", views.StakeholderViewSet)
router.register("milestones", views.MilestoneViewSet)
router.register("communication-items", views.CommunicationItemViewSet)
router.register("activity-notes", views.ActivityNoteViewSet)

urlpatterns = router.urls
