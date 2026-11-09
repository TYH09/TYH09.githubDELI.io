"""
Jours fériés du Cameroun fournis d'office.

Ils sont créés automatiquement par la migration `conges.0008` dès le premier
`manage.py migrate` (donc aussi en production, sans lancer `seed_demo`), et
`seed_demo` appelle `assurer_jours_feries_par_defaut()` pour les recréer au besoin.

Règles :
- les fêtes à date fixe sont « récurrentes » : elles valent chaque année, la
  date stockée (2026) ne sert que de référence ;
- le Vendredi Saint est une fête mobile : il n'est PAS récurrent, sa date change
  chaque année. La RH ajoute celle de l'année suivante dans « Jours fériés » ;
- un jour déjà présent n'est jamais modifié ni dupliqué (même date, ou même
  jour et mois si les deux sont récurrents).

NB : la migration 0008 contient sa propre copie figée de ces valeurs (une
migration ne doit pas dépendre du code applicatif, qui évolue).
"""
from datetime import date

from .models import JourFerie

JOURS_FERIES_PAR_DEFAUT = [
    # (date de référence, libellé, récurrent)
    (date(2026, 1, 1), "Jour de l'An", True),
    (date(2026, 2, 11), "Fête de la Jeunesse", True),
    (date(2026, 4, 3), "Vendredi Saint", False),  # fête mobile
    (date(2026, 5, 1), "Fête du Travail", True),
    (date(2026, 5, 20), "Fête Nationale", True),
    (date(2026, 8, 15), "Assomption", True),
    (date(2026, 12, 25), "Noël", True),
]


def est_deja_present(modele, jour, recurrent):
    """Vrai si ce jour férié existe déjà : même date, ou même jour/mois pour
    deux jours récurrents (évite le doublon « 1er mai 2025 » / « 1er mai 2026 »)."""
    if modele.objects.filter(date=jour).exists():
        return True
    return recurrent and modele.objects.filter(
        recurrent=True, date__month=jour.month, date__day=jour.day
    ).exists()


def assurer_jours_feries_par_defaut(modele=JourFerie):
    """Crée les jours fériés par défaut manquants. Retourne la liste des libellés créés."""
    crees = []
    for jour, libelle, recurrent in JOURS_FERIES_PAR_DEFAUT:
        if est_deja_present(modele, jour, recurrent):
            continue
        modele.objects.create(date=jour, libelle=libelle, recurrent=recurrent)
        crees.append(libelle)
    return crees
