"""
Droits aux congés décomptés du solde.

Congé annuel
    Un employé qui a au moins un an d'ancienneté à l'usine (date d'entrée)
    dispose chaque année d'un solde de congé annuel :
      - 18 jours par défaut ;
      - 21 jours pour une femme dont le dernier enfant a 6 ans ou moins
        (le droit supplémentaire n'existe que si la condition d'un an
        d'ancienneté est remplie).
    Un employé sans ce solde (moins d'un an, ou date d'entrée non renseignée)
    ne peut pas prendre de congé annuel : la règle de solde de
    `DemandeConge.verifier_regles_metier` le refuse.
    Le droit est fixé par ces règles : le plafond du type de congé n'intervient pas.
    Seul le type marqué `est_conge_annuel` suit cette règle.

Autres types décomptés du solde (créés par la RH)
    Chaque employé actif auquel le type est ouvert (cf. `reserve_a_sexe`) dispose
    chaque année d'un solde égal au **plafond** du type, sans condition
    d'ancienneté. Un type décompté du solde sans plafond ne donne aucun solde.

Congé de maternité
    Chaque employée active dispose, chaque année, d'un solde de 90 jours (sans
    condition d'ancienneté), à prendre en une seule fois (cf. règles de la demande).

Les soldes sont créés à la demande (création/modification d'un compte,
consultation du profil, soumission d'une demande) et peuvent être
régularisés en masse par `manage.py synchroniser_soldes` (ex. chaque nuit,
pour les employés qui franchissent leur premier anniversaire).
"""
from django.utils import timezone

from accounts.models import RoleUtilisateur, Sexe, Utilisateur

from .models import DUREE_MATERNITE_JOURS, DemandeConge, SoldeConge, StatutDemande, TypeConge

STATUTS_ACTIFS = [StatutDemande.EN_ATTENTE_MANAGER, StatutDemande.EN_ATTENTE_DIRECTION, StatutDemande.VALIDEE]


def types_conge_annuel():
    """Le « Congé annuel » légal (règle 18/21 jours)."""
    return TypeConge.objects.filter(decompte_solde=True, est_conge_annuel=True, est_maternite=False)


def types_conge_a_plafond():
    """Autres types décomptés du solde : le droit annuel est leur plafond."""
    return TypeConge.objects.filter(
        decompte_solde=True, est_conge_annuel=False, est_maternite=False, plafond_jours__isnull=False,
    )


def types_conge_maternite():
    return TypeConge.objects.filter(est_maternite=True)


def droit_annuel(type_conge, utilisateur):
    """Jours acquis pour l'année par `utilisateur` sur ce type de congé."""
    if type_conge.est_maternite:
        return float(DUREE_MATERNITE_JOURS)
    if type_conge.est_conge_annuel:
        return float(utilisateur.droit_conge_annuel())
    return float(type_conge.plafond_jours or 0)


def _employe_actif(utilisateur):
    return utilisateur.role == RoleUtilisateur.EMPLOYE and utilisateur.actif


def _types_dus(utilisateur):
    """Types de congé pour lesquels l'employé a droit à un solde annuel."""
    if not _employe_actif(utilisateur):
        return []
    dus = []
    if utilisateur.est_eligible_conge_annuel():
        dus.extend(types_conge_annuel())
    dus.extend(t for t in types_conge_a_plafond() if t.est_ouvert_a(utilisateur))
    if utilisateur.sexe == Sexe.FEMININ:
        dus.extend(types_conge_maternite().filter(decompte_solde=True))
    return dus


def synchroniser_soldes(utilisateur, annee=None):
    """Crée, s'ils n'existent pas, les soldes annuels dus à un employé actif :
    congé annuel (≥ 1 an d'ancienneté) et congé de maternité (employées).
    Ne modifie jamais un solde existant. Retourne la liste des soldes créés."""
    annee = annee or timezone.localdate().year
    crees = []
    for type_conge in _types_dus(utilisateur):
        droit = droit_annuel(type_conge, utilisateur)
        solde, cree = SoldeConge.objects.get_or_create(
            utilisateur=utilisateur, type_conge=type_conge, annee=annee,
            defaults={"jours_acquis": droit, "jours_pris": 0, "jours_restants": droit},
        )
        if cree:
            crees.append(solde)
    return crees


def _solde_intact(solde):
    """Aucun jour pris et aucune demande en cours ou validée sur l'année."""
    if solde.jours_pris:
        return False
    return not DemandeConge.objects.filter(
        utilisateur=solde.utilisateur, type_conge=solde.type_conge,
        date_debut__year=solde.annee, statut__in=STATUTS_ACTIFS,
    ).exists()


def retirer_soldes_non_dus(utilisateur):
    """Après correction d'un compte (date d'entrée, sexe, rôle…) : supprime les
    soldes (année en cours et suivantes) qui ne sont plus dus, tant qu'ils sont
    intacts. Un solde déjà entamé n'est jamais touché."""
    dus = {t.pk for t in _types_dus(utilisateur)}
    supprimes = 0
    for solde in SoldeConge.objects.filter(
        utilisateur=utilisateur, type_conge__decompte_solde=True,
        annee__gte=timezone.localdate().year,
    ):
        if solde.type_conge_id not in dus and _solde_intact(solde):
            solde.delete()
            supprimes += 1
    return supprimes


def ajuster_soldes_intacts(utilisateur):
    """Après correction des informations de l'employé (ex. enfant de 6 ans ou
    moins -> 21 jours) : réaligne le droit des soldes intacts (année en cours et
    suivantes). Un solde entamé n'est jamais modifié."""
    ajustes = 0
    for solde in SoldeConge.objects.filter(
        utilisateur=utilisateur, type_conge__decompte_solde=True,
        annee__gte=timezone.localdate().year,
    ).select_related("type_conge"):
        droit = droit_annuel(solde.type_conge, utilisateur)
        if solde.jours_acquis != droit and _solde_intact(solde):
            solde.jours_acquis = droit
            solde.jours_restants = droit
            solde.save(update_fields=["jours_acquis", "jours_restants"])
            ajustes += 1
    return ajustes


def mettre_a_jour_droits(utilisateur):
    """Aligne les soldes sur la situation de l'employé : retire ceux qui ne sont
    plus dus, réajuste ceux qui sont intacts, crée ceux qui sont dus."""
    retirer_soldes_non_dus(utilisateur)
    ajuster_soldes_intacts(utilisateur)
    return synchroniser_soldes(utilisateur)


def propager_type_conge(type_conge):
    """Après création ou modification d'un type de congé : le solde affiché doit
    suivre le plafond défini. Crée les soldes manquants des employés actifs et
    réaligne ceux de CE type qui sont intacts. Ne supprime jamais un solde et ne
    touche jamais un solde entamé. Retourne le nombre de soldes réalignés."""
    annee = timezone.localdate().year
    realignes = 0
    for employe in Utilisateur.objects.filter(role=RoleUtilisateur.EMPLOYE, actif=True):
        synchroniser_soldes(employe)
        for solde in SoldeConge.objects.filter(utilisateur=employe, type_conge=type_conge, annee__gte=annee):
            droit = droit_annuel(type_conge, employe)
            if solde.jours_acquis != droit and _solde_intact(solde):
                solde.jours_acquis = droit
                solde.jours_restants = droit
                solde.save(update_fields=["jours_acquis", "jours_restants"])
                realignes += 1
    return realignes


def synchroniser_tous():
    """Régularisation en masse (tâche planifiée). Retourne le nombre de soldes créés."""
    total = 0
    for employe in Utilisateur.objects.filter(role=RoleUtilisateur.EMPLOYE, actif=True):
        total += len(synchroniser_soldes(employe))
    return total
