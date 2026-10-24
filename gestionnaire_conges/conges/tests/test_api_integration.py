"""
Tests d'intégration de l'API REST, via APIClient (in-process, sans serveur
HTTP réel) : authentification JWT, soumission, workflow à deux niveaux,
dashboard RH, export CSV, notifications, et contrôle des permissions RBAC.
"""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Departement, FonctionDirection, RoleUtilisateur, Utilisateur
from conges.models import SoldeConge, TypeConge


def jour_futur(nb_jours):
    return timezone.localdate() + timedelta(days=nb_jours)


class APIWorkflowTests(APITestCase):
    def setUp(self):
        self.departement = Departement.objects.create(nom="Production")

        self.manager = Utilisateur.objects.create_user(
            username="manager", password="Pass#1234", role=RoleUtilisateur.MANAGER,
            matricule="M1", departement=self.departement,
        )
        self.departement.responsable = self.manager
        self.departement.save()

        self.directeur = Utilisateur.objects.create_user(
            username="directeur", password="Pass#1234", role=RoleUtilisateur.DIRECTEUR,
            matricule="D1", fonction_direction=FonctionDirection.DGA,
        )
        self.rh = Utilisateur.objects.create_user(
            username="rh", password="Pass#1234", role=RoleUtilisateur.RH, matricule="R1",
        )
        self.employe = Utilisateur.objects.create_user(
            username="employe", password="Pass#1234", role=RoleUtilisateur.EMPLOYE,
            matricule="E1", departement=self.departement, email="employe@test.local",
        )

        self.type_cp = TypeConge.objects.create(libelle="Congé annuel", plafond_jours=18, decompte_solde=True)
        SoldeConge.objects.create(
            utilisateur=self.employe, type_conge=self.type_cp, annee=timezone.now().year,
            jours_acquis=18, jours_pris=0, jours_restants=18,
        )

    # -- Authentification --------------------------------------------------
    def test_login_jwt_puis_me(self):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": "employe", "password": "Pass#1234"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        resp_me = self.client.get(reverse("me"))
        self.assertEqual(resp_me.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_me.data["profil"]["username"], "employe")
        self.assertEqual(len(resp_me.data["soldes"]), 1)

    def test_login_echoue_mauvais_mot_de_passe(self):
        resp = self.client.post(
            reverse("token_obtain_pair"), {"username": "employe", "password": "mauvais"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- Workflow complet via l'API -----------------------------------------
    def _soumettre_demande_api(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.post("/api/demandes/", {
            "type_conge": self.type_cp.pk,
            "date_debut": jour_futur(10).isoformat(),
            "date_fin": jour_futur(12).isoformat(),
            "motif": "Congés annuels",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["statut"], "EN_ATTENTE_MANAGER")
        return resp.data["id"]

    def test_circuit_complet_de_bout_en_bout_via_api(self):
        demande_id = self._soumettre_demande_api()

        # Un manager ne peut pas valider au niveau Direction
        self.client.force_authenticate(user=self.manager)
        resp = self.client.post(f"/api/demandes/{demande_id}/valider-direction/", {"decision": "APPROUVE"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Validation manager (1er niveau)
        resp = self.client.post(
            f"/api/demandes/{demande_id}/valider-manager/",
            {"decision": "APPROUVE", "commentaire": "OK pour moi"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["statut"], "EN_ATTENTE_DIRECTION")

        # Un employé ne peut pas s'auto-valider
        self.client.force_authenticate(user=self.employe)
        resp = self.client.post(f"/api/demandes/{demande_id}/valider-direction/", {"decision": "APPROUVE"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Validation Direction Générale (2e niveau, finale)
        self.client.force_authenticate(user=self.directeur)
        resp = self.client.post(
            f"/api/demandes/{demande_id}/valider-direction/",
            {"decision": "APPROUVE", "commentaire": "Validé"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["statut"], "VALIDEE")
        self.assertEqual(len(resp.data["validations"]), 2)

        # Le solde de l'employé a bien été décrémenté du nombre de jours
        # ouvrés réellement couverts par la période (dépend du jour de la
        # semaine courant, donc recalculé ici plutôt que codé en dur).
        jours_ouvres_attendus = sum(
            1 for i in range(3) if (jour_futur(10) + timedelta(days=i)).weekday() < 5
        )
        self.client.force_authenticate(user=self.employe)
        resp = self.client.get(reverse("me"))
        self.assertEqual(resp.data["soldes"][0]["jours_restants"], 18 - jours_ouvres_attendus)

        # Des notifications ont été créées pour l'employé
        resp = self.client.get("/api/notifications/")
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_refus_manager_cloture_le_circuit(self):
        demande_id = self._soumettre_demande_api()
        self.client.force_authenticate(user=self.manager)
        resp = self.client.post(
            f"/api/demandes/{demande_id}/valider-manager/",
            {"decision": "REFUSE", "commentaire": "Effectif insuffisant ce jour-là"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["statut"], "REFUSEE")

    def test_refus_solde_insuffisant_renvoie_400(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.post("/api/demandes/", {
            "type_conge": self.type_cp.pk,
            "date_debut": jour_futur(10).isoformat(),
            "date_fin": jour_futur(40).isoformat(),  # dépasse largement les 18 jours de solde
            "motif": "Trop long",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # -- RH / Dashboard / Export ---------------------------------------------
    def test_dashboard_rh_et_export_csv(self):
        self._soumettre_demande_api()

        self.client.force_authenticate(user=self.rh)
        resp = self.client.get("/api/dashboard/rh/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("demandes_en_attente", resp.data)
        self.assertGreaterEqual(resp.data["demandes_en_attente"], 1)

        resp_csv = self.client.get("/api/export/demandes.csv")
        self.assertEqual(resp_csv.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_csv["Content-Type"].startswith("text/csv"))
        content = b"".join(resp_csv.streaming_content) if resp_csv.streaming else resp_csv.content
        # La demande n'est qu'EN ATTENTE : l'export ne contient que les demandes validées.
        self.assertNotIn(b"E1", content)  # matricule de l'employé de test

    def test_employe_ne_peut_pas_acceder_au_dashboard_rh(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.get("/api/dashboard/rh/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # -- RBAC sur la gestion des comptes --------------------------------------
    def test_seul_administrateur_peut_creer_un_compte(self):
        self.client.force_authenticate(user=self.rh)
        resp = self.client.post("/api/utilisateurs/", {
            "username": "nouveau", "password": "Pass#1234", "matricule": "N1",
            "role": "EMPLOYE",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class APIRoutesComplementairesTests(APIWorkflowTests):
    """Annuaire restreint, changement de mot de passe, réinitialisation
    admin, notifications groupées — routes ajoutées pour le frontend."""

    def test_employe_ne_peut_pas_consulter_l_annuaire(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.get("/api/utilisateurs/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_peut_consulter_l_annuaire_de_son_departement(self):
        self.client.force_authenticate(user=self.manager)
        resp = self.client.get("/api/utilisateurs/", {"departement": self.departement.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 1)

    def test_changer_mon_mot_de_passe(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.post("/api/me/mot-de-passe/", {
            "ancien_mot_de_passe": "Pass#1234", "nouveau_mot_de_passe": "NouveauPass#5678",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.employe.refresh_from_db()
        self.assertTrue(self.employe.check_password("NouveauPass#5678"))

    def test_changer_mon_mot_de_passe_refuse_si_ancien_incorrect(self):
        self.client.force_authenticate(user=self.employe)
        resp = self.client.post("/api/me/mot-de-passe/", {
            "ancien_mot_de_passe": "mauvais", "nouveau_mot_de_passe": "NouveauPass#5678",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_administrateur_peut_reinitialiser_le_mot_de_passe_dun_utilisateur(self):
        admin = Utilisateur.objects.create_user(
            username="admin", password="Pass#1234", role=RoleUtilisateur.ADMINISTRATEUR, matricule="A1",
        )
        self.client.force_authenticate(user=admin)
        resp = self.client.post(
            f"/api/utilisateurs/{self.employe.pk}/definir-mot-de-passe/",
            {"nouveau_mot_de_passe": "Reinit#9999"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.employe.refresh_from_db()
        self.assertTrue(self.employe.check_password("Reinit#9999"))

    def test_rh_ne_peut_pas_reinitialiser_un_mot_de_passe(self):
        self.client.force_authenticate(user=self.rh)
        resp = self.client.post(
            f"/api/utilisateurs/{self.employe.pk}/definir-mot-de-passe/",
            {"nouveau_mot_de_passe": "Reinit#9999"}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_notifications_tout_marquer_lu(self):
        self._soumettre_demande_api()
        self.client.force_authenticate(user=self.employe)
        resp_avant = self.client.get("/api/notifications/", {"lu": "false"})
        self.assertGreaterEqual(resp_avant.data["count"], 1)

        resp = self.client.post("/api/notifications/tout-marquer-lu/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp_apres = self.client.get("/api/notifications/", {"lu": "false"})
        self.assertEqual(resp_apres.data["count"], 0)
