"""Permissions DRF basées sur les rôles (RBAC — CDC §6.6 / §7)."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class EstRH(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.est_rh)


class EstAdministrateur(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.est_administrateur)


class EstRHOuAdministrateur(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.est_rh or u.est_administrateur))


class EstManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.est_manager)


class EstDirecteur(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.est_directeur)


class NestPasSimpleEmploye(BasePermission):
    """Manager, Direction Générale, RH ou Administrateur — exclut le rôle
    Employé. Utilisé pour l'annuaire des utilisateurs : un Employé consulte
    son propre profil via /api/me/, pas l'annuaire complet."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and not u.est_employe)


class LectureSeuleOuRHAdmin(BasePermission):
    """Lecture pour tout utilisateur authentifié ; écriture réservée à la RH
    et à l'Administrateur (ex. TypeConge, JourFerie)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.est_rh or request.user.est_administrateur
