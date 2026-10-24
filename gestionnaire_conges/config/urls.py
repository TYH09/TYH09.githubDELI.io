"""
Routes racine. Toute l'API vit sous /api/ ; /admin/ donne un accès
immédiat (hors frontend React, à construire séparément) aux écrans RH /
Administrateur via l'admin Django, en attendant les interfaces dédiées.
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import ChangerMonMotDePasseView, MeView
from conges.views import (
    AbsencesEquipeView, AlertesSoldeRHView, DashboardRHView, DemandesEnAttenteRHView,
    EmployesSansCongeAnnuelView, ExportDemandesCSVView, ParametresSystemeView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/", MeView.as_view(), name="me"),
    path("api/me/mot-de-passe/", ChangerMonMotDePasseView.as_view(), name="me-mot-de-passe"),
    path("api/equipe/absences/", AbsencesEquipeView.as_view(), name="equipe-absences"),
    path("api/dashboard/rh/", DashboardRHView.as_view(), name="dashboard-rh"),
    path("api/dashboard/rh/demandes-en-attente/", DemandesEnAttenteRHView.as_view(), name="rh-demandes-en-attente"),
    path("api/dashboard/rh/employes-sans-conge-annuel/", EmployesSansCongeAnnuelView.as_view(),
         name="rh-employes-sans-conge-annuel"),
    path("api/dashboard/rh/alertes-solde/", AlertesSoldeRHView.as_view(), name="rh-alertes-solde"),
    path("api/parametres-systeme/", ParametresSystemeView.as_view(), name="parametres-systeme"),
    path("api/export/demandes.csv", ExportDemandesCSVView.as_view(), name="export-demandes-csv"),
    path("api/", include("conges.urls")),
    path("api/", include("accounts.urls")),
]
# Aucune route /media/ publique : les justificatifs (certificats médicaux, etc.)
# ne sortent que par /api/demandes/{id}/justificatif/, derrière authentification
# et contrôle de périmètre.
