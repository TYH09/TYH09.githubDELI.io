from rest_framework.routers import DefaultRouter

from .views import DepartementViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("departements", DepartementViewSet, basename="departement")
router.register("utilisateurs", UtilisateurViewSet, basename="utilisateur")

urlpatterns = router.urls
