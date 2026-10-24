from rest_framework.routers import DefaultRouter

from .views import (
    DemandeCongeViewSet, JournalAuditViewSet, JourFerieViewSet,
    NotificationViewSet, SoldeCongeViewSet, TypeCongeViewSet,
)

router = DefaultRouter()
router.register("types-conge", TypeCongeViewSet, basename="type-conge")
router.register("jours-feries", JourFerieViewSet, basename="jour-ferie")
router.register("soldes", SoldeCongeViewSet, basename="solde-conge")
router.register("demandes", DemandeCongeViewSet, basename="demande-conge")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("journal-audit", JournalAuditViewSet, basename="journal-audit")

urlpatterns = router.urls
