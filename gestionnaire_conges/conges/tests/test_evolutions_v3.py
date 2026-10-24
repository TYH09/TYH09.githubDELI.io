"""
Tests : numéro de téléphone, suppression d'un employé / d'un département par
l'Administrateur, liste des absences de l'équipe pour le Manager.
"""
from datetime import date

from django.test import override_settings

from accounts.models import Departement, RoleUtilisateur, Utilisateur
from conges.models import (
    DemandeConge, JournalAudit, JourFerie, Notification, SoldeConge,
    StatutDemande, date_de_retour,
)

from .test_evolutions_v2 import MEDIA_TMP, BaseV2, creer, jour


def payload(**kw):
    base = {
        "username": "nouveau", "password": "Zx#9kLmN2026", "first_name": "No", "last_name": "Uveau",
        "email": "n@v.local", "matricule": "N1", "role": "EMPLOYE", "sexe": "F", "a_enfant": False,
        "date_embauche": "2020-01-15",
    }
    base.update(kw)
    return base


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class TelephoneTests(BaseV2):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)

    def test_creation_avec_telephone(self):
        resp = self.client.post("/api/utilisateurs/", payload(telephone="  +237 6 70 12 34 56 "), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["telephone"], "+237 6 70 12 34 56")
        self.assertEqual(Utilisateur.objects.get(username="nouveau").telephone, "+237 6 70 12 34 56")

    def test_telephone_facultatif(self):
        resp = self.client.post("/api/utilisateurs/", payload(), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["telephone"], "")

    def test_telephone_invalide_refuse(self):
        for mauvais in ("abc", "12", "+237-@@-123456", "6" * 40):
            resp = self.client.post("/api/utilisateurs/", payload(telephone=mauvais), format="json")
            self.assertEqual(resp.status_code, 400, mauvais)
            self.assertIn("telephone", resp.data)

    def test_formats_courants_acceptes(self):
        for i, bon in enumerate(("670123456", "+237670123456", "(237) 6 70-12-34-56", "237.670.123.456")):
            resp = self.client.post(
                "/api/utilisateurs/", payload(username=f"u{i}", matricule=f"M{i}", telephone=bon), format="json"
            )
            self.assertEqual(resp.status_code, 201, (bon, resp.data))

    def test_modification_et_effacement(self):
        r = self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"telephone": "+237 6 11 22 33 44"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.homme.refresh_from_db()
        self.assertEqual(self.homme.telephone, "+237 6 11 22 33 44")
        r = self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"telephone": ""}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.homme.refresh_from_db()
        self.assertEqual(self.homme.telephone, "")

    def test_numero_visible_dans_l_annuaire_et_dans_mon_profil(self):
        self.homme.telephone = "670123456"
        self.homme.save()
        self.client.force_authenticate(user=self.m_prod)
        annuaire = self.client.get("/api/utilisateurs/?role=EMPLOYE").data["results"]
        self.assertIn("670123456", [u["telephone"] for u in annuaire])
        self.client.force_authenticate(user=self.homme)
        self.assertEqual(self.client.get("/api/me/").data["profil"]["telephone"], "670123456")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SuppressionEmployeTests(BaseV2):
    def test_admin_supprime_un_employe_et_ses_donnees(self):
        self.demande(self.homme, self.cp)
        pk = self.homme.pk
        self.assertTrue(DemandeConge.objects.filter(utilisateur_id=pk).exists())
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"/api/utilisateurs/{pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Utilisateur.objects.filter(pk=pk).exists())
        self.assertFalse(DemandeConge.objects.filter(utilisateur_id=pk).exists())
        self.assertFalse(SoldeConge.objects.filter(utilisateur_id=pk).exists())
        self.assertFalse(Notification.objects.filter(utilisateur_id=pk).exists())

    def test_suppression_journalisee(self):
        self.demande(self.homme, self.cp)
        self.client.force_authenticate(user=self.admin)
        self.client.delete(f"/api/utilisateurs/{self.homme.pk}/")
        entree = JournalAudit.objects.filter(action="Suppression utilisateur").first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.auteur, self.admin)
        self.assertIn("homme", entree.valeur_avant)
        self.assertIn("demandes_supprimees", entree.valeur_avant)

    def test_seul_l_admin_peut_supprimer(self):
        for acteur in (self.rh, self.m_prod, self.dir_a, self.femme):
            self.client.force_authenticate(user=acteur)
            resp = self.client.delete(f"/api/utilisateurs/{self.homme.pk}/")
            self.assertEqual(resp.status_code, 403, acteur.username)
        self.assertTrue(Utilisateur.objects.filter(pk=self.homme.pk).exists())

    def test_non_authentifie(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.delete(f"/api/utilisateurs/{self.homme.pk}/").status_code, 401)

    def test_pas_de_suppression_de_son_propre_compte(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"/api/utilisateurs/{self.admin.pk}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Utilisateur.objects.filter(pk=self.admin.pk).exists())

    def test_un_admin_peut_supprimer_un_autre_admin(self):
        autre = creer("admin2", RoleUtilisateur.ADMINISTRATEUR, sexe="F")
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(f"/api/utilisateurs/{autre.pk}/").status_code, 204)

    def test_compte_inexistant(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete("/api/utilisateurs/999999/").status_code, 404)

    def test_supprimer_un_manager_libere_son_departement(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(f"/api/utilisateurs/{self.m_prod.pk}/").status_code, 204)
        self.prod.refresh_from_db()
        self.assertIsNone(self.prod.responsable)
        self.assertTrue(Departement.objects.filter(pk=self.prod.pk).exists())

    def test_supprimer_un_directeur_detache_ses_departements(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(f"/api/utilisateurs/{self.dir_a.pk}/").status_code, 204)
        self.prod.refresh_from_db()
        self.compta.refresh_from_db()
        self.assertIsNone(self.prod.directeur)
        self.assertIsNone(self.compta.directeur)

    def test_l_historique_des_decisions_survit_a_la_suppression_du_valideur(self):
        d = self.demande(self.homme, self.cp, debut=20, fin=21).data["id"]
        self.client.force_authenticate(user=self.m_prod)
        self.client.post(f"/api/demandes/{d}/valider-manager/", {"decision": "APPROUVE"}, format="json")
        self.client.force_authenticate(user=self.admin)
        self.client.delete(f"/api/utilisateurs/{self.m_prod.pk}/")
        demande = DemandeConge.objects.get(pk=d)
        self.assertEqual(demande.validations.count(), 1)
        self.assertIsNone(demande.validations.first().auteur)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SuppressionDepartementTests(BaseV2):
    def test_admin_supprime_un_departement_vide(self):
        vide = Departement.objects.create(nom="Archives")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"/api/departements/{vide.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Departement.objects.filter(pk=vide.pk).exists())
        entree = JournalAudit.objects.filter(action="Suppression département").first()
        self.assertEqual(entree.auteur, self.admin)
        self.assertIn("Archives", entree.valeur_avant)

    def test_refus_tant_que_des_utilisateurs_y_sont_rattaches(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"/api/departements/{self.logistique.pk}/")  # emp_logi y est rattaché
        self.assertEqual(resp.status_code, 400)
        self.assertIn("1 utilisateur", resp.data["detail"])
        self.assertTrue(Departement.objects.filter(pk=self.logistique.pk).exists())
        self.emp_logi.refresh_from_db()
        self.assertEqual(self.emp_logi.departement, self.logistique)

    def test_possible_apres_reaffectation(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(f"/api/utilisateurs/{self.emp_logi.pk}/", {"departement": self.compta.pk}, format="json")
        self.assertEqual(self.client.delete(f"/api/departements/{self.logistique.pk}/").status_code, 204)

    def test_le_chef_seul_ne_bloque_pas_la_suppression(self):
        seul = Departement.objects.create(nom="Courrier")
        chef = creer("chef_seul", RoleUtilisateur.MANAGER, departement=seul, sexe="M")
        seul.responsable = chef
        seul.directeur = self.dir_a
        seul.save()
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(f"/api/departements/{seul.pk}/").status_code, 204)
        chef.refresh_from_db()
        self.assertIsNone(chef.departement)
        self.assertTrue(Utilisateur.objects.filter(pk=self.dir_a.pk).exists())

    def test_seul_l_admin_supprime_mais_la_rh_garde_creation_et_modification(self):
        vide = Departement.objects.create(nom="Archives")
        for acteur in (self.rh, self.m_prod, self.dir_a, self.homme):
            self.client.force_authenticate(user=acteur)
            self.assertEqual(self.client.delete(f"/api/departements/{vide.pk}/").status_code, 403, acteur.username)
        self.client.force_authenticate(user=self.rh)
        self.assertEqual(self.client.post("/api/departements/", {"nom": "Achats"}, format="json").status_code, 201)
        self.assertEqual(
            self.client.patch(f"/api/departements/{vide.pk}/", {"nom": "Archives 2"}, format="json").status_code, 200
        )
        self.assertTrue(Departement.objects.filter(pk=vide.pk).exists())


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class AbsencesEquipeTests(BaseV2):
    def conge(self, user, debut, fin, statut=StatutDemande.VALIDEE):
        return DemandeConge.objects.create(
            utilisateur=user, type_conge=self.maladie, date_debut=jour(debut), date_fin=jour(fin),
            statut=statut, motif="MOTIF CONFIDENTIEL",
        )

    def setUp(self):
        super().setUp()
        self.homme.telephone = "+237 6 70 00 00 01"
        self.homme.email = "homme@v.local"
        self.homme.first_name, self.homme.last_name = "Henri", "Homme"
        self.homme.save()
        self.femme.first_name, self.femme.last_name = "Fanny", "Femme"
        self.femme.save()
        self.conge(self.femme, -1, 2)            # en cours
        self.conge(self.homme, 5, 7)             # à venir
        self.conge(self.emp_compta, 1, 3)        # autre département
        self.conge(self.homme, 30, 31, StatutDemande.EN_ATTENTE_MANAGER)  # pas validé
        self.conge(self.homme, 40, 41, StatutDemande.REFUSEE)
        self.conge(self.femme, -10, -5)          # terminé
        self.client.force_authenticate(user=self.m_prod)

    def liste(self, **params):
        resp = self.client.get("/api/equipe/absences/", params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_seuls_les_conges_valides_actuels_ou_futurs_de_mon_departement(self):
        data = self.liste()
        self.assertEqual(data["count"], 2)
        self.assertEqual([a["nom_complet"] for a in data["results"]], ["Fanny Femme", "Henri Homme"])
        self.assertEqual([a["statut"] for a in data["results"]], ["EN_COURS", "A_VENIR"])

    def test_champs_exposes(self):
        data = self.liste()
        a = next(x for x in data["results"] if x["utilisateur"] == self.homme.pk)
        self.assertEqual(a["role"], "EMPLOYE")
        self.assertEqual(a["role_affiche"], "Employé")
        self.assertEqual(a["email"], "homme@v.local")
        self.assertEqual(a["telephone"], "+237 6 70 00 00 01")
        self.assertEqual(a["date_depart"], jour(5))
        self.assertEqual(a["date_fin"], jour(7))
        self.assertEqual(a["date_retour"], date_de_retour(jour(7)))
        self.assertGreater(a["date_retour"], a["date_fin"])
        self.assertEqual(a["departement"], "Production")

    def test_type_de_conge_et_motif_jamais_exposes(self):
        brut = str(self.liste())
        for interdit in ("MOTIF CONFIDENTIEL", "maladie", "type_conge", "motif", "justificatif"):
            self.assertNotIn(interdit, brut)

    def test_filtre_periode(self):
        self.assertEqual([a["statut"] for a in self.liste(periode="en_cours")["results"]], ["EN_COURS"])
        self.assertEqual([a["statut"] for a in self.liste(periode="a_venir")["results"]], ["A_VENIR"])
        self.assertEqual(self.client.get("/api/equipe/absences/", {"periode": "x"}).status_code, 400)

    def test_un_manager_ne_voit_pas_les_autres_departements(self):
        self.client.force_authenticate(user=self.m_compta)
        data = self.liste()
        self.assertEqual([a["utilisateur"] for a in data["results"]], [self.emp_compta.pk])

    def test_collaborateur_desactive_exclu(self):
        self.homme.actif = False
        self.homme.save()
        self.assertEqual([a["utilisateur"] for a in self.liste()["results"]], [self.femme.pk])

    def test_reserve_au_manager(self):
        for acteur in (self.homme, self.rh, self.dir_a, self.admin):
            self.client.force_authenticate(user=acteur)
            self.assertEqual(self.client.get("/api/equipe/absences/").status_code, 403, acteur.username)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/equipe/absences/").status_code, 401)

    def test_manager_sans_departement_dirige_voit_une_liste_vide(self):
        sans = creer("m_sans", RoleUtilisateur.MANAGER, sexe="M")
        self.client.force_authenticate(user=sans)
        self.assertEqual(self.liste()["count"], 0)


class DateDeRetourTests(BaseV2):
    def test_apres_un_vendredi_retour_le_lundi(self):
        self.assertEqual(date_de_retour(date(2026, 10, 16)), date(2026, 10, 19))  # 16/10/2026 = vendredi

    def test_en_semaine_retour_le_lendemain(self):
        self.assertEqual(date_de_retour(date(2026, 10, 14)), date(2026, 10, 15))

    def test_saute_un_jour_ferie(self):
        JourFerie.objects.create(date=date(2026, 10, 19), libelle="Fermeture")
        self.assertEqual(date_de_retour(date(2026, 10, 16)), date(2026, 10, 20))

    def test_saute_un_jour_ferie_recurrent_d_une_autre_annee(self):
        JourFerie.objects.create(date=date(2025, 10, 19), libelle="Fête annuelle", recurrent=True)
        self.assertEqual(date_de_retour(date(2026, 10, 16)), date(2026, 10, 20))
