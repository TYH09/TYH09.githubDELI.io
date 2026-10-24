"""
Commande de démonstration : peuple la base avec des départements, des
utilisateurs (un par rôle), des types de congés, des jours fériés 2026
(Cameroun) et des soldes de congés initiaux.

Usage : python manage.py seed_demo
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Departement, FonctionDirection, RoleUtilisateur, Utilisateur
from conges.droits import mettre_a_jour_droits
from conges.models import JourFerie, ParametresSysteme, SoldeConge, TypeConge

JOURS_FERIES_CAMEROUN_2026 = [
    (date(2026, 1, 1), "Jour de l'An"),
    (date(2026, 2, 11), "Fête de la Jeunesse"),
    (date(2026, 4, 3), "Vendredi Saint"),
    (date(2026, 5, 1), "Fête du Travail"),
    (date(2026, 5, 20), "Fête Nationale"),
    (date(2026, 8, 15), "Assomption"),
    (date(2026, 12, 25), "Noël"),
]


class Command(BaseCommand):
    help = "Peuple la base avec des données de démonstration pour le Gestionnaire de Congés."

    def handle(self, *args, **options):
        annee = timezone.now().year

        ParametresSysteme.actuels()

        for d, libelle in JOURS_FERIES_CAMEROUN_2026:
            JourFerie.objects.get_or_create(date=d, defaults={"libelle": libelle, "recurrent": True})

        cp, _ = TypeConge.objects.get_or_create(
            libelle="Congé annuel",
            defaults=dict(plafond_jours=21, justificatif_obligatoire=False, decompte_solde=True,
                          regle_acquisition="18 j/an, 21 j si le dernier enfant a 6 ans ou moins ; dès 1 an d'ancienneté"),
        )
        TypeConge.objects.get_or_create(
            libelle="Congé maladie",
            defaults=dict(plafond_jours=None, justificatif_obligatoire=True,
                          regle_acquisition="sur justificatif médical", decompte_solde=False),
        )
        TypeConge.objects.get_or_create(
            libelle="Congé de paternité",
            defaults=dict(plafond_jours=3, justificatif_obligatoire=True,
                          regle_acquisition="forfaitaire à la naissance", decompte_solde=False,
                          reserve_a_sexe="M"),
        )
        TypeConge.objects.get_or_create(
            libelle="Congé de maternité",
            defaults=dict(plafond_jours=90, justificatif_obligatoire=True, decompte_solde=True,
                          est_maternite=True, reserve_a_sexe="F",
                          regle_acquisition="3 mois par an, pris en 1, 2 ou 3 mois à la fois (30 jours décomptés par mois)"),
        )

        production, _ = Departement.objects.get_or_create(nom="Production")
        rh_dep, _ = Departement.objects.get_or_create(nom="Ressources Humaines")

        def creer_utilisateur(username, prenom, nom, role, sexe, telephone="", **kwargs):
            user, created = Utilisateur.objects.get_or_create(
                username=username,
                defaults=dict(
                    first_name=prenom, last_name=nom, role=role, sexe=sexe, telephone=telephone,
                    email=f"{username}@delifood-agro.local",
                    matricule=kwargs.pop("matricule", username.upper()),
                    **kwargs,
                ),
            )
            if created:
                user.set_password("Conges#2026")
                user.save()
            else:  # base de démo antérieure à l'ajout de champs : on complète sans écraser
                champs = []
                if not user.sexe:
                    user.sexe = sexe
                    champs.append("sexe")
                if not user.telephone and telephone:
                    user.telephone = telephone
                    champs.append("telephone")
                if champs:
                    user.save(update_fields=champs)
            return user

        manager = creer_utilisateur("j.manager", "Jeanne", "Mballa", RoleUtilisateur.MANAGER, "F", telephone="+237 6 70 11 22 33", departement=production)
        production.responsable = manager
        production.save()

        directeur = creer_utilisateur(
            "p.directeur", "Paul", "Ngassa", RoleUtilisateur.DIRECTEUR, "M", telephone="+237 6 99 44 55 66",
            fonction_direction=FonctionDirection.DGA,
        )
        # Le directeur de démonstration supervise plusieurs départements
        for dep in (production, rh_dep):
            if dep.directeur_id is None:
                dep.directeur = directeur
                dep.save(update_fields=["directeur"])
        rh = creer_utilisateur("r.rh", "Rose", "Abena", RoleUtilisateur.RH, "F", telephone="+237 6 77 88 99 00", departement=rh_dep)
        admin = creer_utilisateur("a.admin", "Alain", "Fotso", RoleUtilisateur.ADMINISTRATEUR, "M", telephone="+237 6 55 00 11 22")
        if not admin.is_superuser:
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()

        employe = creer_utilisateur(
            "e.employe", "Eric", "Talla", RoleUtilisateur.EMPLOYE, "M", telephone="+237 6 91 23 45 67",
            departement=production, date_embauche=date(2023, 3, 1),
        )

        # Recrue de moins d'un an : pas encore de droit au congé annuel (aucun solde).
        creer_utilisateur(
            "c.recrue", "Claire", "Mvondo", RoleUtilisateur.EMPLOYE, "F", telephone="+237 6 92 34 56 78",
            departement=production, date_embauche=date.today() - timedelta(days=120), a_enfant=False,
        )

        # Soldes annuels : 18 jours dès un an d'ancienneté (Eric : oui) ; Claire n'a pas de congé annuel
        # (moins d'un an) mais dispose du solde de congé de maternité (90 j).
        for u in (employe, Utilisateur.objects.get(username="c.recrue")):
            mettre_a_jour_droits(u)

        self.stdout.write(self.style.SUCCESS(
            "Données de démonstration créées. Comptes (mot de passe commun : Conges#2026) :\n"
            "  - e.employe   (Employé, plus d'un an d'ancienneté : solde de 18 j)\n"
            "  - c.recrue    (Employée, moins d'un an : pas de congé annuel, solde de maternité de 90 j)\n"
            "  - j.manager   (Manager / chef de département Production)\n"
            "  - p.directeur (Direction Générale — DGA)\n"
            "  - r.rh        (Responsable RH)\n"
            "  - a.admin     (Administrateur, superuser Django admin)"
        ))
