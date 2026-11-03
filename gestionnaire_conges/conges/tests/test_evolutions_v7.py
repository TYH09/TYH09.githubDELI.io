"""
Tests : (1) les types de congé par défaut et leurs règles existent dès la migration,
donc en production, sans `seed_demo` ; (2) un type créé par la RH donne droit à son
plafond, et non plus à 18 ou 21 jours quel que soit le plafond saisi.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import RoleUtilisateur, Utilisateur
from conges.models import SoldeConge, TypeConge
from conges.types_defaut import assurer_types_par_defaut

MDP = "Pass#1234"


def employe(username, sexe, jours_anciennete=365 * 3, **kw):
    return Utilisateur.objects.create_user(
        username=username, password=MDP, role=RoleUtilisateur.EMPLOYE, matricule=username.upper(),
        sexe=sexe, date_embauche=timezone.localdate() - timedelta(days=jours_anciennete), **kw,
    )


class TypesParDefautTests(APITestCase):
    """Base de test = base fraîchement migrée, comme une base de production neuve."""

    def test_les_types_existent_apres_migration_avec_leurs_regles(self):
        types = {t.libelle: t for t in TypeConge.objects.all()}
        self.assertEqual(set(types), {"Congé annuel", "Congé maladie", "Congé de paternité", "Congé de maternité"})

        annuel = types["Congé annuel"]
        self.assertTrue(annuel.est_conge_annuel)
        self.assertTrue(annuel.decompte_solde)
        self.assertIn("18 j/an", annuel.regle_acquisition)

        maladie = types["Congé maladie"]
        self.assertTrue(maladie.justificatif_obligatoire)
        self.assertFalse(maladie.decompte_solde)
        self.assertIsNone(maladie.plafond_jours)

        paternite = types["Congé de paternité"]
        self.assertEqual((paternite.plafond_jours, paternite.reserve_a_sexe), (3, "M"))
        self.assertTrue(paternite.justificatif_obligatoire)
        self.assertFalse(paternite.decompte_solde)

        maternite = types["Congé de maternité"]
        self.assertTrue(maternite.est_maternite)
        self.assertTrue(maternite.decompte_solde)
        self.assertEqual((maternite.plafond_jours, maternite.reserve_a_sexe), (90, "F"))

    def test_assurer_types_par_defaut_est_idempotent(self):
        self.assertEqual(assurer_types_par_defaut(), [])
        self.assertEqual(TypeConge.objects.count(), 4)

    def test_recree_uniquement_le_type_supprime(self):
        TypeConge.objects.get(libelle="Congé maladie").delete()
        self.assertEqual(assurer_types_par_defaut(), ["Congé maladie"])
        self.assertEqual(TypeConge.objects.count(), 4)

    def test_ne_duplique_pas_un_type_renomme_par_la_rh(self):
        TypeConge.objects.filter(est_maternite=True).update(libelle="Congé maternité (usine)")
        TypeConge.objects.filter(est_conge_annuel=True).update(libelle="Congés payés")
        self.assertEqual(assurer_types_par_defaut(), [])
        self.assertEqual(TypeConge.objects.count(), 4)

    def test_un_type_existant_n_est_jamais_modifie(self):
        TypeConge.objects.filter(libelle="Congé de paternité").update(plafond_jours=10)
        assurer_types_par_defaut()
        self.assertEqual(TypeConge.objects.get(libelle="Congé de paternité").plafond_jours, 10)


class PlafondDesTypesTests(APITestCase):
    def setUp(self):
        # Employée éligible dont le dernier enfant a 4 ans : droit annuel de 21 jours.
        self.mere = employe("aminata", "F", a_enfant=True, age_dernier_enfant=4)
        self.homme = employe("paul", "M")
        self.recrue = employe("recrue", "F", jours_anciennete=100, a_enfant=False)
        self.rh = Utilisateur.objects.create_user(
            username="rh", password=MDP, role=RoleUtilisateur.RH, matricule="RH1", sexe="F",
        )
        self.annuel = TypeConge.objects.get(libelle="Congé annuel")

    def creer_type(self, **data):
        self.client.force_authenticate(user=self.rh)
        return self.client.post("/api/types-conge/", data, format="json")

    def modifier_type(self, type_conge, **data):
        self.client.force_authenticate(user=self.rh)
        return self.client.patch(f"/api/types-conge/{type_conge['id'] if isinstance(type_conge, dict) else type_conge.pk}/", data, format="json")

    @staticmethod
    def solde(user, type_conge_id):
        return SoldeConge.objects.filter(
            utilisateur=user, type_conge_id=type_conge_id, annee=timezone.localdate().year
        ).first()

    def jours_sur_le_tableau_de_bord(self, user, type_conge_id):
        """Jours acquis tels que le tableau de bord de l'employé les affiche (GET /me)."""
        self.client.force_authenticate(user=user)
        soldes = self.client.get(reverse("me")).data["soldes"]
        return {s["type_conge"]: s["jours_acquis"] for s in soldes}.get(type_conge_id)

    # --- Le plafond saisi est celui qui s'affiche ---------------------------
    def test_le_plafond_saisi_s_affiche_et_non_21_jours(self):
        r = self.creer_type(libelle="Congé de formation", plafond_jours=5, decompte_solde=True)
        self.assertEqual(r.status_code, 201, r.data)
        type_id = r.data["id"]

        # Dès la création, sans attendre que l'employé ouvre son tableau de bord.
        self.assertEqual(self.solde(self.mere, type_id).jours_acquis, 5)
        self.assertEqual(self.solde(self.homme, type_id).jours_acquis, 5)

        # Et c'est bien ce que voit l'employé sur son tableau de bord.
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, type_id), 5)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.homme, type_id), 5)

    def test_n_importe_quel_plafond_est_respecte(self):
        for plafond in (1, 10, 30):
            r = self.creer_type(libelle=f"Congé {plafond}", plafond_jours=plafond)
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, r.data["id"]), plafond)

    def test_le_conge_annuel_garde_sa_regle_18_ou_21_jours(self):
        self.creer_type(libelle="Congé de formation", plafond_jours=5)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, self.annuel.pk), 21)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.homme, self.annuel.pk), 18)

    def test_modifier_le_plafond_du_conge_annuel_ne_change_pas_le_droit_legal(self):
        self.client.force_authenticate(user=self.rh)
        r = self.client.patch(f"/api/types-conge/{self.annuel.pk}/", {"plafond_jours": 40}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, self.annuel.pk), 21)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.homme, self.annuel.pk), 18)

    def test_aucune_condition_d_anciennete_pour_un_type_a_plafond(self):
        r = self.creer_type(libelle="Congé de formation", plafond_jours=5)
        self.assertEqual(self.solde(self.recrue, r.data["id"]).jours_acquis, 5)
        self.assertIsNone(self.solde(self.recrue, self.annuel.pk))  # < 1 an : pas de congé annuel

    def test_un_type_reserve_a_un_sexe_n_est_ouvert_qu_a_ce_sexe(self):
        r = self.creer_type(libelle="Congé allaitement", plafond_jours=14, reserve_a_sexe="F")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.solde(self.mere, r.data["id"]).jours_acquis, 14)
        self.assertIsNone(self.solde(self.homme, r.data["id"]))

    def test_maternite_et_conge_annuel_ne_sont_pas_perturbes(self):
        self.creer_type(libelle="Congé de formation", plafond_jours=5)
        maternite = TypeConge.objects.get(est_maternite=True)
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, maternite.pk), 90)

    # --- Modification du plafond ---------------------------------------------
    def test_un_plafond_modifie_se_repercute_sur_les_soldes_non_entames_uniquement(self):
        type_id = self.creer_type(libelle="Congé de formation", plafond_jours=5).data["id"]
        entame = self.solde(self.mere, type_id)
        entame.jours_pris, entame.jours_restants = 2, 3
        entame.save()

        r = self.modifier_type(TypeConge.objects.get(pk=type_id), plafond_jours=8)
        self.assertEqual(r.status_code, 200, r.data)

        self.assertEqual(self.solde(self.homme, type_id).jours_acquis, 8)      # intact : réaligné
        self.assertEqual(self.solde(self.homme, type_id).jours_restants, 8)
        entame.refresh_from_db()
        self.assertEqual((entame.jours_acquis, entame.jours_pris, entame.jours_restants), (5, 2, 3))

    def test_modifier_un_seuil_ne_touche_pas_aux_soldes(self):
        type_id = self.creer_type(libelle="Congé de formation", plafond_jours=5).data["id"]
        SoldeConge.objects.filter(type_conge_id=type_id).update(jours_acquis=9, jours_restants=9)
        self.client.force_authenticate(user=Utilisateur.objects.create_user(
            username="adm", password=MDP, role=RoleUtilisateur.ADMINISTRATEUR, matricule="A1", sexe="M",
        ))
        r = self.client.patch(f"/api/types-conge/{type_id}/", {"seuil_alerte_jours": 2}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.solde(self.homme, type_id).jours_acquis, 9)  # pas réaligné : le plafond n'a pas bougé

    # --- Garde-fous de l'API --------------------------------------------------
    def test_un_type_decompte_sans_plafond_est_refuse(self):
        r = self.creer_type(libelle="Congé exceptionnel", decompte_solde=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn("plafond_jours", r.data)
        self.assertFalse(TypeConge.objects.filter(libelle="Congé exceptionnel").exists())

    def test_un_type_non_decompte_peut_ne_pas_avoir_de_plafond(self):
        r = self.creer_type(libelle="Congé exceptionnel", decompte_solde=False)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(SoldeConge.objects.filter(type_conge_id=r.data["id"]).first())

    def test_on_ne_peut_pas_retirer_le_plafond_d_un_type_decompte(self):
        type_id = self.creer_type(libelle="Congé de formation", plafond_jours=5).data["id"]
        r = self.modifier_type(TypeConge.objects.get(pk=type_id), plafond_jours=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn("plafond_jours", r.data)

    def test_le_drapeau_conge_annuel_n_est_pas_modifiable_par_l_api(self):
        r = self.creer_type(
            libelle="Faux congé annuel", plafond_jours=3, decompte_solde=True, est_conge_annuel=True,
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data["est_conge_annuel"])
        self.assertEqual(self.jours_sur_le_tableau_de_bord(self.mere, r.data["id"]), 3)
