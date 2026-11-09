"""
Tests du cœur métier : calcul des jours ouvrés, règles métier, et workflow
de validation à deux niveaux (CDC v1.1 §14.1 "Critères de validation
fonctionnelle").
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Departement, FonctionDirection, RoleUtilisateur, Utilisateur
from conges.models import (
    DemandeConge, JourFerie, RegleMetierError, SoldeConge, StatutDemande, TypeConge,
)
from conges.services import WorkflowError, soumettre_demande, valider_niveau
from conges.models import NiveauValidation, DecisionValidation


def jour_futur(nb_jours):
    return timezone.localdate() + timedelta(days=nb_jours)


class BaseWorkflowTestCase(TestCase):
    def setUp(self):
        self.departement = Departement.objects.create(nom="Production")
        self.manager = Utilisateur.objects.create_user(
            username="manager", password="x", role=RoleUtilisateur.MANAGER,
            matricule="M1", departement=self.departement,
        )
        self.departement.responsable = self.manager
        self.departement.save()

        self.directeur = Utilisateur.objects.create_user(
            username="directeur", password="x", role=RoleUtilisateur.DIRECTEUR,
            matricule="D1", fonction_direction=FonctionDirection.DGA,
        )
        self.employe = Utilisateur.objects.create_user(
            username="employe", password="x", role=RoleUtilisateur.EMPLOYE,
            matricule="E1", departement=self.departement,
        )
        TypeConge.objects.all().delete()  # la migration conges.0007 crée les types par défaut
        JourFerie.objects.all().delete()  # idem conges.0008 : sinon les tests dépendraient de la date du jour
        self.type_cp = TypeConge.objects.create(
            libelle="Congé annuel", plafond_jours=18, decompte_solde=True, est_conge_annuel=True,
        )
        SoldeConge.objects.create(
            utilisateur=self.employe, type_conge=self.type_cp, annee=timezone.now().year,
            jours_acquis=18, jours_pris=0, jours_restants=18,
        )


class CalculJoursOuvresTests(BaseWorkflowTestCase):
    def test_exclut_weekends(self):
        # Lundi à vendredi de la même semaine -> 5 jours ouvrés
        lundi = jour_futur(10)
        while lundi.weekday() != 0:
            lundi += timedelta(days=1)
        demande = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=lundi, date_fin=lundi + timedelta(days=4),
        )
        self.assertEqual(demande.calculer_jours_ouvres(), 5.0)

    def test_exclut_jour_ferie(self):
        lundi = jour_futur(10)
        while lundi.weekday() != 0:
            lundi += timedelta(days=1)
        JourFerie.objects.create(date=lundi + timedelta(days=2), libelle="Jour férié test")
        demande = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=lundi, date_fin=lundi + timedelta(days=4),
        )
        self.assertEqual(demande.calculer_jours_ouvres(), 4.0)


class ReglesMetierTests(BaseWorkflowTestCase):
    def test_refuse_si_solde_insuffisant(self):
        demande = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=jour_futur(10), date_fin=jour_futur(40),  # bien plus que 18 jours ouvrés
        )
        with self.assertRaises(RegleMetierError):
            demande.soumettre()

    def test_refuse_si_delai_minimum_non_respecte(self):
        demande = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=jour_futur(1), date_fin=jour_futur(2),
        )
        with self.assertRaises(RegleMetierError):
            demande.soumettre()

    def test_refuse_si_chevauchement(self):
        d1 = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=jour_futur(10), date_fin=jour_futur(12),
        )
        d1.soumettre()
        d2 = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=jour_futur(11), date_fin=jour_futur(13),
        )
        with self.assertRaises(RegleMetierError):
            d2.soumettre()


class WorkflowDeuxNiveauxTests(BaseWorkflowTestCase):
    """CDC v1.1 §14.1 : "Un employé peut soumettre une demande et voir son
    solde mis à jour après validation finale" + "Le Directeur peut
    approuver ou refuser une demande déjà validée par le chef de
    département"."""

    def _soumettre(self):
        demande = DemandeConge(
            utilisateur=self.employe, type_conge=self.type_cp,
            date_debut=jour_futur(10), date_fin=jour_futur(12),
        )
        return soumettre_demande(demande)

    def test_circuit_nominal_deux_niveaux(self):
        demande = self._soumettre()
        self.assertEqual(demande.statut, StatutDemande.EN_ATTENTE_MANAGER)

        demande = valider_niveau(demande, NiveauValidation.MANAGER, DecisionValidation.APPROUVE, self.manager)
        self.assertEqual(demande.statut, StatutDemande.EN_ATTENTE_DIRECTION)

        solde_avant = SoldeConge.objects.get(utilisateur=self.employe, type_conge=self.type_cp).jours_restants
        demande = valider_niveau(demande, NiveauValidation.DIRECTION, DecisionValidation.APPROUVE, self.directeur)
        self.assertEqual(demande.statut, StatutDemande.VALIDEE)

        solde_apres = SoldeConge.objects.get(utilisateur=self.employe, type_conge=self.type_cp).jours_restants
        self.assertEqual(solde_avant - solde_apres, demande.nb_jours_ouvres)

    def test_refus_manager_cloture_sans_impact_sur_solde(self):
        demande = self._soumettre()
        solde_avant = SoldeConge.objects.get(utilisateur=self.employe, type_conge=self.type_cp).jours_restants

        demande = valider_niveau(
            demande, NiveauValidation.MANAGER, DecisionValidation.REFUSE, self.manager, commentaire="Pic d'activité"
        )
        self.assertEqual(demande.statut, StatutDemande.REFUSEE)

        solde_apres = SoldeConge.objects.get(utilisateur=self.employe, type_conge=self.type_cp).jours_restants
        self.assertEqual(solde_avant, solde_apres)

    def test_refus_direction_apres_approbation_manager(self):
        demande = self._soumettre()
        demande = valider_niveau(demande, NiveauValidation.MANAGER, DecisionValidation.APPROUVE, self.manager)
        demande = valider_niveau(demande, NiveauValidation.DIRECTION, DecisionValidation.REFUSE, self.directeur)
        self.assertEqual(demande.statut, StatutDemande.REFUSEE)
        self.assertEqual(demande.validations.count(), 2)

    def test_impossible_de_valider_a_direction_sans_etape_manager(self):
        demande = self._soumettre()  # encore EN_ATTENTE_MANAGER
        with self.assertRaises(WorkflowError):
            valider_niveau(demande, NiveauValidation.DIRECTION, DecisionValidation.APPROUVE, self.directeur)

    def test_annulation_possible_avant_validation(self):
        demande = self._soumettre()
        demande.annuler()
        self.assertEqual(demande.statut, StatutDemande.ANNULEE)

    def test_annulation_impossible_apres_validation(self):
        demande = self._soumettre()
        demande = valider_niveau(demande, NiveauValidation.MANAGER, DecisionValidation.APPROUVE, self.manager)
        demande = valider_niveau(demande, NiveauValidation.DIRECTION, DecisionValidation.APPROUVE, self.directeur)
        with self.assertRaises(RegleMetierError):
            demande.annuler()
