"""
Types de congé fournis d'office, avec leurs règles.

Ils sont créés automatiquement par la migration `conges.0007` dès le premier
`manage.py migrate` (donc aussi en production, sans lancer `seed_demo`), et
`seed_demo` appelle `assurer_types_par_defaut()` pour les recréer au besoin.

Ne remplace jamais un type existant : un type déjà présent (même renommé ou
modifié par la RH) est laissé tel quel.

NB : la migration 0007 contient sa propre copie figée de ces valeurs (une
migration ne doit pas dépendre du code applicatif, qui évolue).
"""
from django.db.models import Q

from .models import TypeConge

TYPES_PAR_DEFAUT = [
    {
        "existe": Q(est_conge_annuel=True) | Q(libelle="Congé annuel"),
        "libelle": "Congé annuel",
        "defaults": dict(
            plafond_jours=21, justificatif_obligatoire=False, decompte_solde=True, est_conge_annuel=True,
            regle_acquisition="18 j/an, 21 j si le dernier enfant a 6 ans ou moins ; dès 1 an d'ancienneté",
        ),
    },
    {
        "existe": Q(libelle__icontains="maladie"),
        "libelle": "Congé maladie",
        "defaults": dict(
            plafond_jours=None, justificatif_obligatoire=True, decompte_solde=False,
            regle_acquisition="sur justificatif médical",
        ),
    },
    {
        "existe": Q(libelle__icontains="paternité"),
        "libelle": "Congé de paternité",
        "defaults": dict(
            plafond_jours=3, justificatif_obligatoire=True, decompte_solde=False, reserve_a_sexe="M",
            regle_acquisition="forfaitaire à la naissance",
        ),
    },
    {
        "existe": Q(est_maternite=True) | Q(libelle="Congé de maternité"),
        "libelle": "Congé de maternité",
        "defaults": dict(
            plafond_jours=90, justificatif_obligatoire=True, decompte_solde=True, est_maternite=True,
            reserve_a_sexe="F",
            regle_acquisition="3 mois par an, pris en 1, 2 ou 3 mois à la fois (30 jours décomptés par mois)",
        ),
    },
]


def assurer_types_par_defaut(modele=TypeConge):
    """Crée les types par défaut manquants. Retourne la liste des libellés créés."""
    crees = []
    for definition in TYPES_PAR_DEFAUT:
        if modele.objects.filter(definition["existe"]).exists():
            continue
        modele.objects.create(libelle=definition["libelle"], **definition["defaults"])
        crees.append(definition["libelle"])
    return crees
