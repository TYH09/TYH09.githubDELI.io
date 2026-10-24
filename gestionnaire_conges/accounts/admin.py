from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Departement, Utilisateur


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ("nom", "responsable", "directeur")
    search_fields = ("nom",)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = (
        "username", "matricule", "get_full_name", "telephone", "sexe", "role",
        "fonction_direction", "departement", "actif", "is_active",
    )
    list_filter = ("role", "sexe", "fonction_direction", "departement", "actif")
    search_fields = ("username", "matricule", "first_name", "last_name", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Informations métier (Gestionnaire de Congés)", {
            "fields": ("matricule", "telephone", "sexe", "role", "fonction_direction", "departement", "date_embauche", "actif"),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Informations métier (Gestionnaire de Congés)", {
            "fields": ("matricule", "telephone", "sexe", "role", "fonction_direction", "departement", "date_embauche"),
        }),
    )
