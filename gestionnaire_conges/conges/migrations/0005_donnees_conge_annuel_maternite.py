"""
Migration de données :
- « Congé payé » devient « Congé annuel » ;
- « Congé sans solde » est supprimé (s'il n'a jamais servi : une demande existante
  protège le type, qui est alors conservé) ;
- le congé de maternité est décompté du solde (90 jours calendaires, une fois par an) ;
- les jours décomptés des demandes existantes reprennent leurs jours ouvrés.
"""
from django.db import migrations
from django.db.models import F


def appliquer(apps, schema_editor):
    TypeConge = apps.get_model("conges", "TypeConge")
    DemandeConge = apps.get_model("conges", "DemandeConge")

    if not TypeConge.objects.filter(libelle="Congé annuel").exists():
        TypeConge.objects.filter(libelle="Congé payé").update(libelle="Congé annuel")

    for sans_solde in TypeConge.objects.filter(libelle="Congé sans solde"):
        if not DemandeConge.objects.filter(type_conge=sans_solde).exists():
            sans_solde.delete()

    for maternite in TypeConge.objects.filter(libelle__icontains="maternité"):
        maternite.est_maternite = True
        maternite.decompte_solde = True
        maternite.plafond_jours = 90
        maternite.reserve_a_sexe = "F"
        maternite.regle_acquisition = "90 jours par an, une seule fois (1+2, 2+1 ou 3 mois autour du terme)"
        maternite.save()

    DemandeConge.objects.update(nb_jours_decomptes=F("nb_jours_ouvres"))


class Migration(migrations.Migration):
    dependencies = [("conges", "0004_maternite_et_jours_decomptes")]
    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
