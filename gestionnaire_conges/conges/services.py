"""
Couche "service" : orchestre les transitions du workflow à deux niveaux,
telles que décrites dans les diagrammes de séquence de l'analyse UML
(Fragment 1 — Soumission, Fragment 2 — Validation Manager,
Fragment 3 — Validation Direction Générale).

Centraliser cette logique ici (plutôt que dans les vues) permet de la
réutiliser à l'identique depuis l'API DRF, l'admin Django ou les tests,
et correspond à la remarque de l'analyse UML : "un argument pour une API
factorisée (une route paramétrée par niveau, plutôt que deux routes
dupliquées)".
"""
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .droits import synchroniser_soldes
from .models import (
    DecisionValidation,
    JournalAudit,
    NiveauValidation,
    Notification,
    RegleMetierError,
    SoldeConge,
    StatutDemande,
    Validation,
)


def _journaliser(auteur, action, entite_concernee, avant="", apres=""):
    JournalAudit.objects.create(
        auteur=auteur,
        action=action,
        entite_concernee=entite_concernee,
        valeur_avant=str(avant),
        valeur_apres=str(apres),
    )


def _notifier(utilisateur, message, demande=None):
    Notification.objects.create(utilisateur=utilisateur, demande=demande, message=message)
    if utilisateur.email:
        send_mail(
            subject="Gestionnaire de Congés — mise à jour",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[utilisateur.email],
            fail_silently=True,
        )


class WorkflowError(RegleMetierError):
    """Erreur de transition de workflow (ex. mauvais niveau, demande déjà close)."""


@transaction.atomic
def soumettre_demande(demande):
    """Fragment 1 — Soumission (diagramme de séquence 1/2)."""
    avant = demande.statut
    # Un employé éligible (≥ 1 an d'ancienneté) dispose de son solde annuel : on le
    # crée s'il manque (année de la demande, au plus l'année suivante).
    annee_courante = timezone.localdate().year
    if demande.date_debut.year in (annee_courante, annee_courante + 1):
        synchroniser_soldes(demande.utilisateur, demande.date_debut.year)
    demande.soumettre()  # calcule les jours ouvrés + vérifie les règles métier
    _journaliser(demande.utilisateur, "Soumission demande de congé", f"DemandeConge#{demande.pk}", avant, demande.statut)

    manager = getattr(demande.utilisateur.departement, "responsable", None)
    if manager:
        _notifier(
            manager,
            f"Nouvelle demande de congé de {demande.utilisateur.get_full_name()} à valider.",
            demande,
        )
    _notifier(demande.utilisateur, "Votre demande de congé a bien été soumise.", demande)
    return demande


def _verifier_niveau(demande, niveau_attendu):
    attendu = {
        NiveauValidation.MANAGER: StatutDemande.EN_ATTENTE_MANAGER,
        NiveauValidation.DIRECTION: StatutDemande.EN_ATTENTE_DIRECTION,
    }[niveau_attendu]
    if demande.statut != attendu:
        raise WorkflowError(
            f"Cette demande n'est pas en attente de validation à ce niveau (statut actuel : {demande.statut})."
        )


@transaction.atomic
def valider_niveau(demande, niveau, decision, auteur, commentaire=""):
    """Fragment 2 (Manager) / Fragment 3 (Direction Générale) — même patron
    d'interaction pour les deux niveaux du circuit."""
    _verifier_niveau(demande, niveau)
    avant = demande.statut

    Validation.objects.create(
        demande=demande, niveau=niveau, decision=decision, auteur=auteur, commentaire=commentaire
    )
    _journaliser(
        auteur,
        f"Décision {niveau.lower()} : {decision}",
        f"DemandeConge#{demande.pk}",
        avant,
        decision,
    )

    if decision == DecisionValidation.REFUSE:
        demande.statut = StatutDemande.REFUSEE
        demande.save(update_fields=["statut", "date_maj"])
        _notifier(
            demande.utilisateur,
            f"Votre demande de congé a été refusée au niveau « {niveau} »"
            + (f" : {commentaire}" if commentaire else "."),
            demande,
        )
        return demande

    if niveau == NiveauValidation.MANAGER:
        demande.statut = StatutDemande.EN_ATTENTE_DIRECTION
        demande.save(update_fields=["statut", "date_maj"])
        for directeur in _directeurs_pour(demande):
            _notifier(
                directeur,
                f"Une demande approuvée par le chef de département requiert votre validation "
                f"({demande.utilisateur.get_full_name()}).",
                demande,
            )
        return demande

    # niveau == DIRECTION, décision == APPROUVE -> validation finale
    demande.statut = StatutDemande.VALIDEE
    demande.save(update_fields=["statut", "date_maj"])
    if demande.type_conge.decompte_solde:
        solde, _ = SoldeConge.objects.get_or_create(
            utilisateur=demande.utilisateur,
            type_conge=demande.type_conge,
            annee=demande.date_debut.year,
        )
        solde.mettre_a_jour(-demande.nb_jours_decomptes)
    _notifier(demande.utilisateur, "Votre demande de congé a été validée.", demande)
    return demande


def _directeurs_pour(demande):
    """Directeurs appelés à statuer sur la demande : ceux qui supervisent le
    département de l'employé ; à défaut (département sans directeur affecté,
    ou employé sans département), toute la Direction Générale active — la
    demande ne reste ainsi jamais sans décideur."""
    from accounts.models import RoleUtilisateur, Utilisateur

    directeurs = Utilisateur.objects.filter(role=RoleUtilisateur.DIRECTEUR, actif=True)
    departement = demande.utilisateur.departement
    if departement and departement.directeur_id:
        return directeurs.filter(pk=departement.directeur_id)
    return directeurs
