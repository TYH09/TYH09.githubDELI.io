"""
Tests : délai minimum et seuil d'alerte propres à chaque type de congé,
configurés par l'Administrateur (la RH définit les types mais ne règle pas
ces deux seuils) ; l'export est uniquement CSV.
"""
from django.test import override_settings
from django.utils import timezone

from conges.models import JournalAudit, ParametresSysteme, SoldeConge

from .test_evolutions_v2 import MEDIA_TMP, BaseV2
from .test_evolutions_v4 import ouvre


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class SeuilsParTypeDeCongeTests(BaseV2):
    def url(self, type_conge):
        return f"/api/types-conge/{type_conge.pk}/"

    def patch(self, acteur, type_conge, **data):
        self.client.force_authenticate(user=acteur)
        return self.client.patch(self.url(type_conge), data, format="json")

    # --- Qui peut configurer ---------------------------------------------
    def test_l_admin_configure_delai_et_seuil_d_un_type(self):
        r = self.patch(self.admin, self.cp, delai_minimum_jours=10, seuil_alerte_jours=5)
        self.assertEqual(r.status_code, 200, r.data)
        self.cp.refresh_from_db()
        self.assertEqual((self.cp.delai_minimum_jours, self.cp.seuil_alerte_jours), (10, 5))
        self.assertEqual((r.data["delai_minimum_effectif"], r.data["seuil_alerte_effectif"]), (10, 5))

    def test_la_modification_est_inscrite_au_journal_d_audit(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=7)
        entree = JournalAudit.objects.get(action="Seuils du type de congé modifiés")
        self.assertEqual(entree.auteur, self.admin)
        self.assertIn("Congé annuel", entree.entite_concernee)
        self.assertIn("7", entree.valeur_apres)

    def test_la_rh_ne_peut_pas_regler_les_seuils(self):
        r = self.patch(self.rh, self.cp, delai_minimum_jours=10)
        self.assertEqual(r.status_code, 400)
        self.assertIn("delai_minimum_jours", r.data)
        r = self.patch(self.rh, self.cp, seuil_alerte_jours=1)
        self.assertEqual(r.status_code, 400)
        self.cp.refresh_from_db()
        self.assertIsNone(self.cp.delai_minimum_jours)
        self.assertIsNone(self.cp.seuil_alerte_jours)

    def test_la_rh_cree_un_type_sans_seuils_mais_pas_avec(self):
        self.client.force_authenticate(user=self.rh)
        r = self.client.post(
            "/api/types-conge/", {"libelle": "Congé formation", "decompte_solde": False}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["delai_minimum_jours"])
        r = self.client.post(
            "/api/types-conge/",
            {"libelle": "Autre", "decompte_solde": False, "delai_minimum_jours": 4}, format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("delai_minimum_jours", r.data)

    def test_la_rh_garde_la_main_sur_la_definition_du_type(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=10)
        r = self.patch(self.rh, self.cp, plafond_jours=20)
        self.assertEqual(r.status_code, 200, r.data)
        self.cp.refresh_from_db()
        self.assertEqual((self.cp.plafond_jours, self.cp.delai_minimum_jours), (20, 10))

    def test_put_complet_de_la_rh_avec_seuils_inchanges_est_accepte(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=10)
        self.client.force_authenticate(user=self.rh)
        corps = self.client.get(self.url(self.cp)).data
        corps["plafond_jours"] = 19
        r = self.client.put(self.url(self.cp), corps, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_les_autres_roles_ne_peuvent_pas_modifier(self):
        for acteur in (self.homme, self.m_prod, self.dir_a):
            self.assertEqual(self.patch(acteur, self.cp, delai_minimum_jours=1).status_code, 403, acteur.username)

    def test_valeurs_invalides_refusees(self):
        self.assertEqual(self.patch(self.admin, self.cp, delai_minimum_jours=-1).status_code, 400)
        self.assertEqual(self.patch(self.admin, self.cp, seuil_alerte_jours=366).status_code, 400)

    def test_vider_le_champ_revient_au_parametre_systeme(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=10)
        r = self.patch(self.admin, self.cp, delai_minimum_jours=None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["delai_minimum_effectif"], ParametresSysteme.actuels().delai_minimum_jours)

    def test_valeur_effective_suit_le_parametre_systeme_tant_que_le_type_n_a_pas_la_sienne(self):
        params = ParametresSysteme.actuels()
        params.delai_minimum_jours, params.seuil_alerte_solde_jours = 8, 6
        params.save()
        self.client.force_authenticate(user=self.admin)
        donnees = {t["libelle"]: t for t in self.client.get("/api/types-conge/").data["results"]}
        self.assertEqual(donnees["Congé annuel"]["delai_minimum_effectif"], 8)
        self.assertEqual(donnees["Congé annuel"]["seuil_alerte_effectif"], 6)

    # --- Application des règles ------------------------------------------
    def test_delai_propre_au_type_applique_a_la_soumission(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=10)
        trop_tot = self.demande(self.homme, self.cp, debut=ouvre(5), fin=ouvre(5))
        self.assertEqual(trop_tot.status_code, 400)
        self.assertIn("10 jour(s)", str(trop_tot.data))
        self.assertIn("Congé annuel", str(trop_tot.data))
        assez_tard = self.demande(self.homme, self.cp, debut=ouvre(10), fin=ouvre(10))
        self.assertEqual(assez_tard.status_code, 201, assez_tard.data)

    def test_un_type_sans_delai_propre_garde_le_parametre_systeme(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=30)  # ne concerne que le congé annuel
        r = self.demande(self.homme, self.maladie, fichier=self.pdf(), debut=ouvre(5), fin=ouvre(5))
        self.assertEqual(r.status_code, 201, r.data)

    def test_delai_du_type_plus_court_que_le_parametre_systeme(self):
        self.patch(self.admin, self.cp, delai_minimum_jours=0)
        r = self.demande(self.homme, self.cp, debut=ouvre(1), fin=ouvre(1))
        self.assertEqual(r.status_code, 201, r.data)  # le défaut système (3 j) aurait refusé

    def test_alertes_solde_faible_utilisent_le_seuil_du_type(self):
        annee = timezone.now().year
        SoldeConge.objects.filter(type_conge=self.cp).update(jours_restants=8)  # 4 soldes à 8 jours
        self.client.force_authenticate(user=self.rh)

        def alertes():
            self.client.force_authenticate(user=self.rh)
            return self.client.get("/api/dashboard/rh/").data["alertes_solde_faible"]

        self.assertEqual(alertes(), 0)                       # seuil système : 3 jours
        self.patch(self.admin, self.cp, seuil_alerte_jours=8)
        self.assertEqual(alertes(), 4)                       # seuil du type : 8 jours
        self.patch(self.admin, self.cp, seuil_alerte_jours=7)
        self.assertEqual(alertes(), 0)
        self.assertEqual(SoldeConge.objects.filter(annee=annee).count(), 4)
