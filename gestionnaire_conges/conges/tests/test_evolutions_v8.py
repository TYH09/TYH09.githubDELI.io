"""
Tests : (1) les jours fériés du Cameroun existent dès la migration, donc en production,
sans `seed_demo` ; (2) un jour férié « récurrent » est bien exclu du décompte des jours
ouvrés chaque année (avant, seule l'année exacte comptait).
"""
from datetime import date
from io import StringIO

from django.core.management import call_command
from rest_framework.test import APITestCase

from accounts.models import RoleUtilisateur, Utilisateur
from conges.jours_feries_defaut import assurer_jours_feries_par_defaut
from conges.models import DemandeConge, JourFerie

MDP = "Pass#1234"

ATTENDUS = {
    date(2026, 1, 1): ("Jour de l'An", True),
    date(2026, 2, 11): ("Fête de la Jeunesse", True),
    date(2026, 4, 3): ("Vendredi Saint", False),
    date(2026, 5, 1): ("Fête du Travail", True),
    date(2026, 5, 20): ("Fête Nationale", True),
    date(2026, 8, 15): ("Assomption", True),
    date(2026, 12, 25): ("Noël", True),
}


def jours_ouvres(debut, fin):
    return DemandeConge(date_debut=debut, date_fin=fin).calculer_jours_ouvres()


class JoursFeriesParDefautTests(APITestCase):
    """Base de test = base fraîchement migrée, comme une base de production neuve."""

    def test_les_jours_feries_existent_apres_migration(self):
        presents = {j.date: (j.libelle, j.recurrent) for j in JourFerie.objects.all()}
        self.assertEqual(presents, ATTENDUS)

    def test_le_vendredi_saint_est_une_fete_mobile_non_recurrente(self):
        self.assertFalse(JourFerie.objects.get(libelle="Vendredi Saint").recurrent)
        self.assertEqual(JourFerie.objects.filter(recurrent=True).count(), 6)

    def test_ils_sont_visibles_par_un_employe_via_l_api(self):
        employe = Utilisateur.objects.create_user(
            username="emp", password=MDP, role=RoleUtilisateur.EMPLOYE, matricule="E1",
            sexe="M", date_embauche=date(2020, 1, 1),
        )
        self.client.force_authenticate(user=employe)
        r = self.client.get("/api/jours-feries/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({j["libelle"] for j in r.data["results"]}, {v[0] for v in ATTENDUS.values()})

    def test_assurer_jours_feries_est_idempotent(self):
        self.assertEqual(assurer_jours_feries_par_defaut(), [])
        self.assertEqual(JourFerie.objects.count(), 7)

    def test_recree_uniquement_le_jour_supprime(self):
        JourFerie.objects.get(libelle="Noël").delete()
        self.assertEqual(assurer_jours_feries_par_defaut(), ["Noël"])
        self.assertEqual(JourFerie.objects.count(), 7)

    def test_un_jour_modifie_par_la_rh_n_est_jamais_ecrase(self):
        JourFerie.objects.filter(libelle="Noël").update(libelle="Noël (usine fermée)")
        assurer_jours_feries_par_defaut()
        self.assertEqual(JourFerie.objects.get(date=date(2026, 12, 25)).libelle, "Noël (usine fermée)")
        self.assertEqual(JourFerie.objects.count(), 7)

    def test_ne_duplique_pas_un_jour_recurrent_cree_pour_une_autre_annee(self):
        # La RH avait saisi « 1er mai 2025, récurrent » : pas de doublon « 1er mai 2026 ».
        JourFerie.objects.get(date=date(2026, 5, 1)).delete()
        JourFerie.objects.create(date=date(2025, 5, 1), libelle="Fête du travail", recurrent=True)
        self.assertEqual(assurer_jours_feries_par_defaut(), [])
        self.assertEqual(JourFerie.objects.filter(date__month=5, date__day=1).count(), 1)

    def test_seed_demo_ne_cree_pas_de_doublons_et_peut_etre_relance(self):
        for _ in range(2):
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(JourFerie.objects.count(), 7)

    def test_seed_demo_recree_un_jour_ferie_supprime(self):
        JourFerie.objects.all().delete()
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual({j.date for j in JourFerie.objects.all()}, set(ATTENDUS))


class JoursOuvresEtJoursFeriesRecurrentsTests(APITestCase):
    """Les jours fériés par défaut (base migrée) sont pris en compte dans le décompte."""

    def test_un_ferie_recurrent_est_exclu_l_annee_de_reference(self):
        # Noël 2026 tombe un vendredi : lundi 21 → vendredi 25 = 4 jours ouvrés
        self.assertEqual(jours_ouvres(date(2026, 12, 21), date(2026, 12, 25)), 4.0)

    def test_un_ferie_recurrent_est_exclu_les_annees_suivantes(self):
        # Fête de la Jeunesse (11 février) 2027 = jeudi : lundi 8 → vendredi 12 = 4 jours ouvrés
        # (avant la correction : 5, car seule la date exacte de 2026 comptait).
        self.assertEqual(jours_ouvres(date(2027, 2, 8), date(2027, 2, 12)), 4.0)

    def test_une_semaine_sans_ferie_compte_cinq_jours(self):
        self.assertEqual(jours_ouvres(date(2027, 2, 15), date(2027, 2, 19)), 5.0)

    def test_le_vendredi_saint_est_exclu_l_annee_de_reference(self):
        # Vendredi Saint 2026 = vendredi 3 avril : lundi 30 mars → vendredi 3 avril = 4 jours
        self.assertEqual(jours_ouvres(date(2026, 3, 30), date(2026, 4, 3)), 4.0)

    def test_le_vendredi_saint_n_est_pas_repete_les_annees_suivantes(self):
        # Fête mobile : le 3 avril 2028 (lundi) n'est pas férié. Lundi 3 → vendredi 7 = 5 jours.
        self.assertEqual(jours_ouvres(date(2028, 4, 3), date(2028, 4, 7)), 5.0)

    def test_un_ferie_non_recurrent_d_une_autre_annee_n_est_pas_exclu(self):
        JourFerie.objects.create(date=date(2026, 3, 4), libelle="Fermeture exceptionnelle")
        self.assertEqual(jours_ouvres(date(2027, 3, 1), date(2027, 3, 5)), 5.0)

    def test_un_ferie_recurrent_ajoute_par_la_rh_vaut_chaque_annee(self):
        JourFerie.objects.create(date=date(2026, 3, 4), libelle="Fête de l'usine", recurrent=True)
        self.assertEqual(jours_ouvres(date(2027, 3, 1), date(2027, 3, 5)), 4.0)  # jeudi 4 mars 2027
