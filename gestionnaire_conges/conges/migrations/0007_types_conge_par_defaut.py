"""
1. Ajoute `TypeConge.est_conge_annuel` : désigne le « Congé annuel » légal, seul type
   dont le droit suit la règle 18/21 jours. Les autres types décomptés du solde
   donnent droit à leur plafond (avant, ils recevaient tous 18 ou 21 jours).
2. Crée, s'ils n'existent pas, les types de congé fournis d'office avec leurs règles,
   pour qu'ils soient présents en production sans passer par `seed_demo`.

Aucun type existant n'est modifié, hormis le marquage du « Congé annuel ».
Copie figée de `conges.types_defaut` (une migration ne dépend pas du code applicatif).
"""
from django.db import migrations, models
from django.db.models import Q

TYPES_PAR_DEFAUT = [
    (Q(est_conge_annuel=True) | Q(libelle="Congé annuel"), "Congé annuel", dict(
        plafond_jours=21, justificatif_obligatoire=False, decompte_solde=True, est_conge_annuel=True,
        regle_acquisition="18 j/an, 21 j si le dernier enfant a 6 ans ou moins ; dès 1 an d'ancienneté",
    )),
    (Q(libelle__icontains="maladie"), "Congé maladie", dict(
        plafond_jours=None, justificatif_obligatoire=True, decompte_solde=False,
        regle_acquisition="sur justificatif médical",
    )),
    (Q(libelle__icontains="paternité"), "Congé de paternité", dict(
        plafond_jours=3, justificatif_obligatoire=True, decompte_solde=False, reserve_a_sexe="M",
        regle_acquisition="forfaitaire à la naissance",
    )),
    (Q(est_maternite=True) | Q(libelle="Congé de maternité"), "Congé de maternité", dict(
        plafond_jours=90, justificatif_obligatoire=True, decompte_solde=True, est_maternite=True,
        reserve_a_sexe="F",
        regle_acquisition="3 mois par an, pris en 1, 2 ou 3 mois à la fois (30 jours décomptés par mois)",
    )),
]


def creer_types_par_defaut(apps, schema_editor):
    TypeConge = apps.get_model("conges", "TypeConge")

    # Base existante : le « Congé annuel » déjà en place suit la règle 18/21 jours.
    TypeConge.objects.filter(libelle="Congé annuel").update(est_conge_annuel=True)

    for existe, libelle, defaults in TYPES_PAR_DEFAUT:
        if not TypeConge.objects.filter(existe).exists():
            TypeConge.objects.create(libelle=libelle, **defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("conges", "0006_maternite_duree_en_mois"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconge",
            name="est_conge_annuel",
            field=models.BooleanField(
                default=False,
                help_text="Congé annuel légal : le droit n'est pas le plafond mais 18 jours par an (21 pour une femme dont le dernier enfant a 6 ans ou moins), dès 1 an d'ancienneté. Réglage de structure : les autres types décomptés du solde donnent droit à leur plafond annuel.",
            ),
        ),
        migrations.RunPython(creer_types_par_defaut, migrations.RunPython.noop),
    ]
