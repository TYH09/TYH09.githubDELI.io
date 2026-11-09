"""
Crée, s'ils n'existent pas, les jours fériés du Cameroun fournis d'office, pour
qu'ils soient présents en production sans passer par `seed_demo`.

Aucun jour férié existant n'est modifié ni dupliqué : un jour est ignoré si sa date
existe déjà, ou si un jour récurrent tombe déjà le même jour et le même mois.
Le Vendredi Saint (fête mobile) n'est pas récurrent.

Copie figée de `conges.jours_feries_defaut` (une migration ne dépend pas du code
applicatif). Non réversible : on ne supprime pas des données que la RH a pu modifier.
"""
from datetime import date

from django.db import migrations

JOURS_FERIES_PAR_DEFAUT = [
    (date(2026, 1, 1), "Jour de l'An", True),
    (date(2026, 2, 11), "Fête de la Jeunesse", True),
    (date(2026, 4, 3), "Vendredi Saint", False),
    (date(2026, 5, 1), "Fête du Travail", True),
    (date(2026, 5, 20), "Fête Nationale", True),
    (date(2026, 8, 15), "Assomption", True),
    (date(2026, 12, 25), "Noël", True),
]


def creer_jours_feries(apps, schema_editor):
    JourFerie = apps.get_model("conges", "JourFerie")
    for jour, libelle, recurrent in JOURS_FERIES_PAR_DEFAUT:
        deja = JourFerie.objects.filter(date=jour).exists() or (
            recurrent
            and JourFerie.objects.filter(recurrent=True, date__month=jour.month, date__day=jour.day).exists()
        )
        if not deja:
            JourFerie.objects.create(date=jour, libelle=libelle, recurrent=recurrent)


class Migration(migrations.Migration):

    dependencies = [
        ("conges", "0007_types_conge_par_defaut"),
    ]

    operations = [
        migrations.RunPython(creer_jours_feries, migrations.RunPython.noop),
    ]
