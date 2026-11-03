from django.contrib import admin

from .models import (
    DemandeConge, JournalAudit, JourFerie, Notification,
    ParametresSysteme, SoldeConge, TypeConge, Validation,
)


@admin.register(TypeConge)
class TypeCongeAdmin(admin.ModelAdmin):
    list_display = ("libelle", "plafond_jours", "justificatif_obligatoire", "decompte_solde", "reserve_a_sexe",
                    "est_conge_annuel", "est_maternite", "delai_minimum_jours", "seuil_alerte_jours")


@admin.register(SoldeConge)
class SoldeCongeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type_conge", "annee", "jours_acquis", "jours_pris", "jours_restants")
    list_filter = ("annee", "type_conge")
    search_fields = ("utilisateur__username", "utilisateur__first_name", "utilisateur__last_name")


class ValidationInline(admin.TabularInline):
    model = Validation
    extra = 0
    readonly_fields = ("niveau", "decision", "auteur", "commentaire", "date_validation")
    can_delete = False


@admin.register(DemandeConge)
class DemandeCongeAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "type_conge", "date_debut", "date_fin", "nb_jours_ouvres", "statut")
    list_filter = ("statut", "type_conge")
    search_fields = ("utilisateur__username", "utilisateur__first_name", "utilisateur__last_name")
    inlines = [ValidationInline]
    readonly_fields = ("nb_jours_ouvres", "date_creation", "date_maj")


@admin.register(JourFerie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = ("date", "libelle", "recurrent")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "message", "date_envoi", "lu")
    list_filter = ("lu",)


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date_action", "auteur", "action", "entite_concernee")
    list_filter = ("action",)
    readonly_fields = [f.name for f in JournalAudit._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ParametresSysteme)
class ParametresSystemeAdmin(admin.ModelAdmin):
    list_display = ("delai_minimum_jours", "seuil_alerte_solde_jours")

    def has_add_permission(self, request):
        return not ParametresSysteme.objects.exists()
