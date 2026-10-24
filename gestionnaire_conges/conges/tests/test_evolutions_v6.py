"""
Tests : droit de 18 ou 21 jours de congé annuel selon l'enfant de l'employée,
congé de maternité (3 mois par an décomptés du solde, pris en 1, 2 ou 3 mois à la fois,
date de fin calculée) et listes détaillées du tableau de bord RH.
"""
from datetime import date, timedelta

from django.test import override_settings
from django.utils import timezone

from accounts.models import Utilisateur
from conges.models import (
    DemandeConge, DecisionValidation, NiveauValidation, SoldeConge, StatutDemande, Validation,
)

from .test_evolutions_v2 import MEDIA_TMP, BaseV2, creer, jour
from .test_evolutions_v4 import il_y_a, il_y_a_annees, ouvre, payload


def solde_annuel(user, type_conge, annee=None):
    return SoldeConge.objects.filter(
        utilisateur=user, type_conge=type_conge, annee=annee or timezone.localdate().year
    ).first()


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EnfantEtDroitAnnuelTests(BaseV2):
    def creer(self, **kw):
        self.client.force_authenticate(user=self.admin)
        return self.client.post("/api/utilisateurs/", payload(**kw), format="json")

    def solde(self, username):
        return solde_annuel(Utilisateur.objects.get(username=username), self.cp)

    # --- Saisie à la création ---------------------------------------------
    def test_une_employee_doit_indiquer_si_elle_a_un_enfant(self):
        r = self.creer(a_enfant=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn("a_enfant", r.data)
        payload_sans = payload()
        payload_sans.pop("a_enfant")
        self.client.force_authenticate(user=self.admin)
        r = self.client.post("/api/utilisateurs/", payload_sans, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("a_enfant", r.data)

    def test_avec_enfant_l_age_du_dernier_est_obligatoire(self):
        r = self.creer(a_enfant=True)
        self.assertEqual(r.status_code, 400)
        self.assertIn("age_dernier_enfant", r.data)

    def test_age_negatif_ou_aberrant_refuse(self):
        self.assertEqual(self.creer(a_enfant=True, age_dernier_enfant=-1).status_code, 400)
        self.assertEqual(self.creer(a_enfant=True, age_dernier_enfant=99).status_code, 400)

    def test_sans_enfant_l_age_est_efface(self):
        r = self.creer(a_enfant=False, age_dernier_enfant=4)
        self.assertEqual(r.status_code, 201, r.data)
        u = Utilisateur.objects.get(username="nouveau")
        self.assertIs(u.a_enfant, False)
        self.assertIsNone(u.age_dernier_enfant)

    def test_un_homme_n_a_pas_a_renseigner_d_enfant(self):
        r = self.creer(sexe="M", a_enfant=None)
        self.assertEqual(r.status_code, 201, r.data)
        u = Utilisateur.objects.get(username="nouveau")
        self.assertIsNone(u.a_enfant)
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)

    def test_un_homme_avec_des_champs_enfant_les_voit_ignores(self):
        r = self.creer(sexe="M", a_enfant=True, age_dernier_enfant=2)
        self.assertEqual(r.status_code, 201, r.data)
        u = Utilisateur.objects.get(username="nouveau")
        self.assertIsNone(u.a_enfant)
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)  # pas de majoration pour un homme

    # --- Droit : 18 ou 21 jours ---------------------------------------------
    def test_dernier_enfant_de_plus_de_6_ans_18_jours(self):
        self.assertEqual(self.creer(a_enfant=True, age_dernier_enfant=7).status_code, 201)
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)

    def test_dernier_enfant_de_6_ans_exactement_21_jours(self):
        self.assertEqual(self.creer(a_enfant=True, age_dernier_enfant=6).status_code, 201)
        self.assertEqual(self.solde("nouveau").jours_acquis, 21)
        self.assertEqual(self.solde("nouveau").jours_restants, 21)

    def test_dernier_enfant_de_moins_de_6_ans_et_nouveau_ne_21_jours(self):
        for age, nom in ((0, "bebe"), (3, "petit")):
            self.assertEqual(self.creer(username=nom, matricule=nom, email=f"{nom}@v.local",
                                        a_enfant=True, age_dernier_enfant=age).status_code, 201)
            self.assertEqual(self.solde(nom).jours_acquis, 21, nom)

    def test_sans_enfant_18_jours(self):
        self.assertEqual(self.creer(a_enfant=False).status_code, 201)
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)

    def test_la_majoration_exige_un_an_d_anciennete(self):
        r = self.creer(a_enfant=True, age_dernier_enfant=2, date_embauche=str(il_y_a(200)))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(self.solde("nouveau"))                       # ni 18 ni 21 jours avant un an
        self.assertEqual(r.data["droit_conge_annuel"], None)

    def test_le_profil_expose_le_droit(self):
        r = self.creer(a_enfant=True, age_dernier_enfant=2)
        self.assertEqual(r.data["droit_conge_annuel"], 21)
        self.assertEqual(r.data["age_dernier_enfant"], 2)
        r = self.creer(username="autre", matricule="A2", email="a@v.local", a_enfant=False)
        self.assertEqual(r.data["droit_conge_annuel"], 18)

    # --- Modification -------------------------------------------------------
    def modifier(self, pk, **data):
        self.client.force_authenticate(user=self.admin)
        return self.client.patch(f"/api/utilisateurs/{pk}/", data, format="json")

    def test_corriger_l_enfant_realigne_un_solde_intact(self):
        self.creer(a_enfant=True, age_dernier_enfant=9)
        u = Utilisateur.objects.get(username="nouveau")
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)
        self.assertEqual(self.modifier(u.pk, age_dernier_enfant=4).status_code, 200)
        self.assertEqual(self.solde("nouveau").jours_acquis, 21)
        self.assertEqual(self.modifier(u.pk, a_enfant=False).status_code, 200)
        self.assertEqual(self.solde("nouveau").jours_acquis, 18)

    def test_un_solde_entame_n_est_pas_modifie(self):
        self.creer(a_enfant=False)
        u = Utilisateur.objects.get(username="nouveau")
        s = self.solde("nouveau")
        s.jours_pris, s.jours_restants = 5, 13
        s.save()
        self.assertEqual(self.modifier(u.pk, a_enfant=True, age_dernier_enfant=1).status_code, 200)
        s.refresh_from_db()
        self.assertEqual((s.jours_acquis, s.jours_restants), (18, 13))

    def test_modification_sans_rapport_d_un_ancien_compte_sans_info_enfant(self):
        # compte de femme antérieur à la fonctionnalité : a_enfant jamais renseigné
        self.assertIsNone(self.femme.a_enfant)
        self.assertEqual(self.modifier(self.femme.pk, first_name="Fanny").status_code, 200)

    def test_toucher_au_sexe_ou_au_role_oblige_a_renseigner_l_enfant(self):
        r = self.modifier(self.homme.pk, sexe="F")
        self.assertEqual(r.status_code, 400)
        self.assertIn("a_enfant", r.data)
        r = self.modifier(self.homme.pk, sexe="F", a_enfant=True, age_dernier_enfant=5)
        self.assertEqual(r.status_code, 200, r.data)

    def test_un_ancien_compte_sans_info_enfant_a_18_jours(self):
        self.assertEqual(self.femme.droit_conge_annuel(), 18)

    def test_seul_l_admin_modifie_ces_informations(self):
        self.client.force_authenticate(user=self.rh)
        r = self.client.patch(f"/api/utilisateurs/{self.femme.pk}/", {"a_enfant": True, "age_dernier_enfant": 2}, format="json")
        self.assertEqual(r.status_code, 403)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class CongeMaterniteTests(BaseV2):
    def setUp(self):
        super().setUp()
        self.mat.est_maternite = True
        self.mat.decompte_solde = True
        self.mat.save()
        for u in (self.femme, self.emp_compta, self.homme):
            u.first_name, u.last_name = u.username.capitalize(), "Test"
            u.date_embauche = il_y_a_annees(3)
            u.save()
        self.annee = timezone.localdate().year + 1   # dates fixes : indépendant du jour du test

    def jours_jusqu_a(self, d):
        return (d - timezone.localdate()).days

    def demander(self, user=None, mois=1, debut=None, **extra):
        self.client.force_authenticate(user=user or self.femme)
        data = {"type_conge": self.mat.pk, "date_debut": jour(debut or ouvre(10)).isoformat(),
                "duree_maternite_mois": mois, "justificatif_fichier": self.pdf()}
        data.update(extra)
        data = {k: v for k, v in data.items() if v is not None}
        return self.client.post("/api/demandes/", data, format="multipart")

    def demander_en(self, mois, mois_depart, user=None):
        """Demande de `mois` mois qui démarre le 1er du mois `mois_depart` de l'année suivante."""
        return self.demander(user=user, mois=mois, debut=self.jours_jusqu_a(date(self.annee, mois_depart, 1)))

    def decider(self, demande_id, niveau, acteur, decision="APPROUVE"):
        self.client.force_authenticate(user=acteur)
        chemin = "valider-manager" if niveau == "manager" else "valider-direction"
        return self.client.post(f"/api/demandes/{demande_id}/{chemin}/", {"decision": decision}, format="json")

    def valider(self, demande_id):
        self.assertEqual(self.decider(demande_id, "manager", self.m_prod).status_code, 200)
        self.assertEqual(self.decider(demande_id, "direction", self.dir_a).status_code, 200)

    def options(self, user=None):
        """Durées (en mois) que l'API annonce encore disponibles pour l'année suivante."""
        self.client.force_authenticate(user=user or self.femme)
        r = self.client.get("/api/soldes/", {"annee": self.annee, "type_conge": self.mat.pk})
        self.assertEqual(r.status_code, 200)
        resultats = r.data["results"] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(resultats), 1)
        return resultats[0]["mois_disponibles"]

    def existante(self, debut, mois, statut=StatutDemande.EN_ATTENTE_MANAGER):
        return DemandeConge.objects.create(
            utilisateur=self.femme, type_conge=self.mat, date_debut=debut, duree_maternite_mois=mois,
            date_fin=debut + timedelta(days=30 * mois - 1), nb_jours_decomptes=30 * mois, statut=statut,
        )

    # --- Durée, date de fin et date de retour -----------------------------------
    def test_la_date_de_fin_depend_de_la_duree_choisie(self):
        for i, (mois, jours) in enumerate(((1, 30), (2, 60), (3, 90))):
            employee = creer(f"mere{i}", "EMPLOYE", departement=self.prod, sexe="F",
                             date_embauche=il_y_a_annees(2), a_enfant=False)
            r = self.demander(user=employee, mois=mois)
            self.assertEqual(r.status_code, 201, (mois, r.data))
            debut = jour(ouvre(10))
            self.assertEqual(r.data["duree_maternite_mois"], mois)
            self.assertEqual(r.data["date_fin"], str(debut + timedelta(days=jours - 1)))
            self.assertEqual(r.data["nb_jours_decomptes"], jours)
            self.assertEqual(r.data["statut"], "EN_ATTENTE_MANAGER")
        self.assertLess(r.data["nb_jours_ouvres"], 90)   # jours calendaires = ouvrés + non ouvrés

    def test_la_date_de_retour_est_le_premier_jour_de_travail_apres_la_fin(self):
        for mois in (1, 2, 3):
            employee = creer(f"retour{mois}", "EMPLOYE", departement=self.prod, sexe="F",
                             date_embauche=il_y_a_annees(2), a_enfant=False)
            r = self.demander(user=employee, mois=mois)
            fin = date.fromisoformat(r.data["date_fin"])
            retour = date.fromisoformat(r.data["date_retour"])
            self.assertGreater(retour, fin)
            self.assertLess(retour.weekday(), 5)

    def test_la_date_de_fin_saisie_par_le_client_est_ignoree(self):
        r = self.demander(mois=2, date_fin=str(jour(ouvre(12))))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["date_fin"], str(jour(ouvre(10)) + timedelta(days=59)))

    def test_la_duree_est_obligatoire_et_controlee(self):
        self.assertEqual(self.demander(mois=None).status_code, 400)
        for invalide in (0, 4, "", "abc"):
            self.assertEqual(self.demander(mois=invalide).status_code, 400, invalide)

    def test_la_duree_n_a_pas_de_sens_pour_un_autre_type(self):
        self.client.force_authenticate(user=self.femme)
        r = self.client.post("/api/demandes/", {
            "type_conge": self.cp.pk, "date_debut": str(jour(ouvre(10))), "date_fin": str(jour(ouvre(10))),
            "duree_maternite_mois": 1,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_un_autre_type_exige_toujours_une_date_de_fin(self):
        self.client.force_authenticate(user=self.femme)
        r = self.client.post("/api/demandes/", {"type_conge": self.cp.pk, "date_debut": str(jour(ouvre(10)))}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_fin", r.data)

    # --- 3 mois par an, à prendre en 1, 2 ou 3 mois -----------------------------
    def test_apres_1_mois_il_reste_les_options_1_mois_et_2_mois(self):
        r = self.demander_en(1, 1)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.options(), [1, 2])
        refus = self.demander_en(3, 6)
        self.assertEqual(refus.status_code, 400)
        self.assertIn("1 mois ou 2 mois", str(refus.data))
        self.assertEqual(self.demander_en(2, 6).status_code, 201)     # 2 mois : accepté
        self.assertEqual(self.options(), [])

    def test_apres_2_mois_la_seule_option_restante_est_1_mois(self):
        self.assertEqual(self.demander_en(2, 1).status_code, 201)
        self.assertEqual(self.options(), [1])
        for mois in (2, 3):
            refus = self.demander_en(mois, 6)
            self.assertEqual(refus.status_code, 400, mois)
            self.assertIn("Il ne vous reste que 1 mois", str(refus.data))
        self.assertEqual(self.demander_en(1, 6).status_code, 201)
        self.assertEqual(self.options(), [])

    def test_apres_3_mois_plus_d_acces_au_conge_de_maternite_cette_annee(self):
        self.assertEqual(self.demander_en(3, 1).status_code, 201)
        self.assertEqual(self.options(), [])
        for mois in (1, 2, 3):
            refus = self.demander_en(mois, 6)
            self.assertEqual(refus.status_code, 400, mois)
            self.assertIn("plus disponible cette année", str(refus.data))

    def test_trois_fois_un_mois_puis_plus_rien(self):
        for depart in (1, 4, 7):
            self.assertEqual(self.demander_en(1, depart).status_code, 201, depart)
        self.assertEqual(self.options(), [])
        self.assertEqual(self.demander_en(1, 10).status_code, 400)

    def test_une_demande_validee_compte_aussi(self):
        self.existante(date(self.annee, 1, 1), 2, StatutDemande.VALIDEE)
        refus = self.demander_en(2, 6)
        self.assertEqual(refus.status_code, 400)
        self.assertEqual(self.demander_en(1, 6).status_code, 201)

    def test_une_demande_refusee_ou_annulee_libere_les_mois(self):
        r = self.demander_en(3, 1)
        self.assertEqual(self.options(), [])
        self.client.force_authenticate(user=self.femme)
        self.assertEqual(self.client.post(f"/api/demandes/{r.data['id']}/annuler/").status_code, 200)
        self.assertEqual(self.options(), [1, 2, 3])
        refusee = self.demander_en(2, 1)
        self.decider(refusee.data["id"], "manager", self.m_prod, decision="REFUSE")
        self.assertEqual(self.options(), [1, 2, 3])
        self.assertEqual(self.demander_en(3, 6).status_code, 201)

    def test_l_annee_suivante_repart_a_3_mois(self):
        self.existante(date(timezone.localdate().year, 12, 20), 3)   # année courante : engagée
        r = self.demander(mois=3, debut=self.jours_jusqu_a(date(self.annee, 6, 1)))
        self.assertEqual(r.status_code, 201, r.data)

    def test_le_decompte_du_solde_se_fait_a_la_validation_finale(self):
        r = self.demander_en(2, 1)
        solde = SoldeConge.objects.get(utilisateur=self.femme, type_conge=self.mat, annee=self.annee)
        self.assertEqual((solde.jours_acquis, solde.jours_restants), (90, 90))   # pas encore débité
        self.valider(r.data["id"])
        solde.refresh_from_db()
        self.assertEqual((solde.jours_pris, solde.jours_restants), (60, 30))
        self.assertEqual(DemandeConge.objects.get(pk=r.data["id"]).statut, StatutDemande.VALIDEE)
        self.assertEqual(self.options(), [1])

    def test_validee_et_en_attente_se_cumulent_dans_les_options(self):
        r = self.demander_en(1, 1)
        self.valider(r.data["id"])
        self.assertEqual(self.options(), [1, 2])
        self.assertEqual(self.demander_en(1, 6).status_code, 201)     # en attente
        self.assertEqual(self.options(), [1])

    def test_le_solde_expose_jours_engages_et_disponibles(self):
        self.demander_en(1, 1)
        self.client.force_authenticate(user=self.femme)
        solde = self.client.get("/api/soldes/", {"annee": self.annee, "type_conge": self.mat.pk}).data["results"][0]
        self.assertEqual((solde["jours_restants"], solde["jours_engages"], solde["jours_disponibles"]), (90, 30, 60))
        self.assertTrue(solde["est_maternite"])

    def test_le_conge_annuel_n_a_pas_de_mois_disponibles(self):
        from conges.droits import mettre_a_jour_droits

        mettre_a_jour_droits(self.femme)
        self.client.force_authenticate(user=self.femme)
        soldes = self.client.get("/api/soldes/", {"type_conge": self.cp.pk}).data["results"]
        self.assertTrue(soldes)
        self.assertIsNone(soldes[0]["mois_disponibles"])

    # --- Autres règles -----------------------------------------------------------
    def test_la_maternite_est_reservee_aux_femmes(self):
        r = self.demander(user=self.homme)
        self.assertEqual(r.status_code, 400)
        self.assertIn("réservé aux femmes", str(r.data))

    def test_pas_de_condition_d_anciennete_pour_la_maternite(self):
        recrue = creer("recrue", "EMPLOYE", departement=self.prod, sexe="F",
                       date_embauche=il_y_a(60), a_enfant=False)
        r = self.demander(user=recrue)
        self.assertEqual(r.status_code, 201, r.data)
        # ... alors que le congé annuel lui est refusé (moins d'un an)
        self.client.force_authenticate(user=recrue)
        r = self.client.post("/api/demandes/", {
            "type_conge": self.cp.pk, "date_debut": str(jour(ouvre(40))), "date_fin": str(jour(ouvre(40))),
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_le_justificatif_reste_obligatoire(self):
        self.client.force_authenticate(user=self.femme)
        r = self.client.post("/api/demandes/", {
            "type_conge": self.mat.pk, "date_debut": str(jour(ouvre(10))), "duree_maternite_mois": 1,
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("justificatif", str(r.data).lower())

    def test_le_delai_minimum_s_applique_a_la_date_de_depart(self):
        r = self.demander(debut=1)
        self.assertEqual(r.status_code, 400)
        self.assertIn("délai minimum", str(r.data))

    def test_chevauchement_avec_un_conge_annuel_refuse(self):
        DemandeConge.objects.create(
            utilisateur=self.femme, type_conge=self.cp, date_debut=jour(ouvre(20)), date_fin=jour(ouvre(20)),
            nb_jours_ouvres=1, nb_jours_decomptes=1, statut=StatutDemande.EN_ATTENTE_MANAGER,
        )
        r = self.demander(mois=2)   # les 60 jours englobent ouvre(20)
        self.assertEqual(r.status_code, 400)
        self.assertIn("chevauche", str(r.data))

    def test_une_employee_a_son_solde_de_maternite_les_autres_non(self):
        from conges.droits import mettre_a_jour_droits

        for u in (self.femme, self.homme):
            mettre_a_jour_droits(u)
        annee = timezone.localdate().year
        self.assertEqual(solde_annuel(self.femme, self.mat, annee).jours_acquis, 90)
        self.assertIsNone(solde_annuel(self.homme, self.mat, annee))

    def test_la_maternite_ne_declenche_pas_d_alerte_de_solde_faible(self):
        r = self.demander(mois=3)
        self.valider(r.data["id"])                                   # solde de maternité : 0 jour restant
        annee = jour(ouvre(10)).year
        self.client.force_authenticate(user=self.rh)
        data = self.client.get("/api/dashboard/rh/alertes-solde/", {"annee": annee}).data
        self.assertNotIn("Congé de maternité", [a["type_conge"] for a in data["results"]])

    def test_la_maternite_ne_compte_pas_comme_conge_annuel_pris(self):
        r = self.demander(mois=3)
        self.valider(r.data["id"])
        self.client.force_authenticate(user=self.rh)
        annee = jour(ouvre(10)).year
        noms = [e["nom_complet"] for e in
                self.client.get("/api/dashboard/rh/employes-sans-conge-annuel/", {"annee": annee}).data["results"]]
        self.assertIn(self.femme.get_full_name(), noms)

    def test_export_csv_indique_les_jours_decomptes(self):
        r = self.demander(mois=2)
        self.valider(r.data["id"])
        self.client.force_authenticate(user=self.rh)
        texte = self.client.get("/api/export/demandes.csv").content.decode("utf-8-sig")
        ligne = [l for l in texte.splitlines() if "maternité" in l][0]
        self.assertTrue(ligne.rstrip().endswith(",60"))


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class ListesDuTableauDeBordRHTests(BaseV2):
    def setUp(self):
        super().setUp()
        for u in (self.homme, self.femme, self.emp_compta, self.emp_logi):
            u.first_name, u.last_name = u.username.capitalize(), "Test"   # noms distincts
            u.date_embauche = il_y_a_annees(3)
            u.save()
        self.femme.date_embauche = il_y_a(100)   # recrue : non éligible
        self.femme.save()
        self.annee = timezone.localdate().year
        self.client.force_authenticate(user=self.rh)

    def get(self, chemin, **params):
        return self.client.get(f"/api/dashboard/rh/{chemin}/", params)

    def demande(self, user, statut, type_conge=None, debut=10):
        return DemandeConge.objects.create(
            utilisateur=user, type_conge=type_conge or self.cp, date_debut=jour(debut), date_fin=jour(debut + 1),
            nb_jours_ouvres=2, nb_jours_decomptes=2, statut=statut,
        )

    # --- Demandes en attente --------------------------------------------------
    def test_demandes_en_attente_avec_niveau_et_historique(self):
        d1 = self.demande(self.homme, StatutDemande.EN_ATTENTE_MANAGER)
        d2 = self.demande(self.emp_compta, StatutDemande.EN_ATTENTE_DIRECTION, debut=20)
        Validation.objects.create(demande=d2, niveau=NiveauValidation.MANAGER,
                                  decision=DecisionValidation.APPROUVE, auteur=self.m_compta, commentaire="OK chef")
        for statut in (StatutDemande.VALIDEE, StatutDemande.REFUSEE, StatutDemande.ANNULEE, StatutDemande.BROUILLON):
            self.demande(self.emp_logi, statut, debut=30)
        data = self.get("demandes-en-attente").data
        self.assertEqual(data["count"], 2)
        par_id = {d["id"]: d for d in data["results"]}
        self.assertEqual(set(par_id), {d1.pk, d2.pk})
        self.assertEqual(par_id[d1.pk]["statut"], "EN_ATTENTE_MANAGER")
        self.assertEqual(par_id[d1.pk]["validations"], [])
        self.assertEqual(par_id[d2.pk]["statut"], "EN_ATTENTE_DIRECTION")
        self.assertEqual(par_id[d2.pk]["validations"][0]["niveau"], "MANAGER")
        self.assertEqual(par_id[d2.pk]["validations"][0]["decision"], "APPROUVE")
        self.assertEqual(par_id[d2.pk]["utilisateur_detail"]["departement_nom"], "Comptabilité")
        self.assertEqual(par_id[d2.pk]["type_conge_libelle"], "Congé annuel")

    def test_le_chiffre_du_tableau_de_bord_egale_la_liste(self):
        self.demande(self.homme, StatutDemande.EN_ATTENTE_MANAGER)
        self.demande(self.emp_compta, StatutDemande.EN_ATTENTE_DIRECTION, debut=20)
        self.assertEqual(self.get("demandes-en-attente").data["count"], self.client.get("/api/dashboard/rh/").data["demandes_en_attente"])

    # --- Employés éligibles sans congé annuel -------------------------------------
    def test_employes_eligibles_sans_conge_annuel_et_leur_departement(self):
        self.demande(self.homme, StatutDemande.VALIDEE)                       # a pris son congé annuel
        data = self.get("employes-sans-conge-annuel", annee=jour(10).year).data
        noms = {e["nom_complet"]: e for e in data["results"]}
        self.assertEqual(set(noms), {self.emp_compta.get_full_name(), self.emp_logi.get_full_name()})
        self.assertEqual(noms[self.emp_compta.get_full_name()]["departement"], "Comptabilité")
        self.assertEqual(noms[self.emp_logi.get_full_name()]["departement"], "Logistique")
        self.assertEqual(noms[self.emp_logi.get_full_name()]["droit_conge_annuel"], 18)
        self.assertEqual(noms[self.emp_logi.get_full_name()]["jours_restants"], 18)
        self.assertEqual(data["count"], 2)

    def test_le_droit_affiche_tient_compte_de_l_enfant(self):
        self.emp_compta.a_enfant, self.emp_compta.age_dernier_enfant = True, 4
        self.emp_compta.save()
        data = self.get("employes-sans-conge-annuel", annee=self.annee).data
        ligne = [e for e in data["results"] if e["utilisateur"] == self.emp_compta.pk][0]
        self.assertEqual(ligne["droit_conge_annuel"], 21)

    def test_les_non_eligibles_n_y_figurent_pas(self):
        noms = [e["nom_complet"] for e in self.get("employes-sans-conge-annuel", annee=self.annee).data["results"]]
        self.assertNotIn(self.femme.get_full_name(), noms)

    def test_un_autre_type_de_conge_ne_retire_pas_de_la_liste(self):
        self.demande(self.emp_logi, StatutDemande.VALIDEE, type_conge=self.maladie)
        noms = [e["nom_complet"] for e in self.get("employes-sans-conge-annuel", annee=jour(10).year).data["results"]]
        self.assertIn(self.emp_logi.get_full_name(), noms)

    def test_un_conge_annuel_non_valide_ou_d_une_autre_annee_ne_retire_pas(self):
        self.demande(self.emp_logi, StatutDemande.REFUSEE)
        DemandeConge.objects.create(
            utilisateur=self.emp_compta, type_conge=self.cp, date_debut=date(self.annee - 1, 5, 4),
            date_fin=date(self.annee - 1, 5, 5), nb_jours_ouvres=2, statut=StatutDemande.VALIDEE,
        )
        noms = [e["nom_complet"] for e in self.get("employes-sans-conge-annuel", annee=jour(10).year).data["results"]]
        self.assertEqual(set(noms), {self.homme.get_full_name(), self.emp_compta.get_full_name(), self.emp_logi.get_full_name()})

    def test_les_comptes_desactives_sont_ignores(self):
        self.emp_logi.actif = False
        self.emp_logi.save()
        noms = [e["nom_complet"] for e in self.get("employes-sans-conge-annuel", annee=self.annee).data["results"]]
        self.assertNotIn(self.emp_logi.get_full_name(), noms)

    def test_le_chiffre_du_tableau_de_bord_egale_la_liste_des_sans_conge(self):
        self.demande(self.homme, StatutDemande.VALIDEE)
        annee = jour(10).year
        self.assertEqual(
            self.get("employes-sans-conge-annuel", annee=annee).data["count"],
            self.client.get("/api/dashboard/rh/", {"annee": annee}).data["salaries_sans_conge_annuel"],
        )

    # --- Alertes de solde faible ----------------------------------------------
    def test_alertes_de_solde_faible(self):
        SoldeConge.objects.filter(utilisateur=self.homme).update(jours_restants=2)
        SoldeConge.objects.filter(utilisateur=self.emp_compta).update(jours_restants=3)   # = seuil par défaut (3)
        SoldeConge.objects.filter(utilisateur=self.emp_logi).update(jours_restants=4)     # au-dessus
        data = self.get("alertes-solde", annee=self.annee).data
        self.assertEqual(data["count"], 2)
        noms = [a["nom_complet"] for a in data["results"]]
        self.assertEqual(noms, [self.homme.get_full_name(), self.emp_compta.get_full_name()])   # plus faibles d'abord
        premiere = data["results"][0]
        self.assertEqual(premiere["departement"], "Production")
        self.assertEqual(premiere["type_conge"], "Congé annuel")
        self.assertEqual((premiere["jours_restants"], premiere["seuil_alerte"]), (2, 3))

    def test_alertes_utilisent_le_seuil_du_type_et_les_comptes_actifs(self):
        SoldeConge.objects.filter(type_conge=self.cp).update(jours_restants=10)
        self.cp.seuil_alerte_jours = 10
        self.cp.save()
        self.emp_logi.actif = False
        self.emp_logi.save()
        data = self.get("alertes-solde", annee=self.annee).data
        self.assertEqual(data["count"], 3)   # homme, femme, emp_compta (emp_logi désactivé)
        self.assertTrue(all(a["seuil_alerte"] == 10 for a in data["results"]))

    def test_le_chiffre_du_tableau_de_bord_egale_la_liste_des_alertes(self):
        SoldeConge.objects.filter(utilisateur=self.homme).update(jours_restants=0)
        self.assertEqual(
            self.get("alertes-solde", annee=self.annee).data["count"],
            self.client.get("/api/dashboard/rh/").data["alertes_solde_faible"],
        )

    # --- Accès ----------------------------------------------------------------
    def test_acces_reserve_rh_et_admin(self):
        for chemin in ("demandes-en-attente", "employes-sans-conge-annuel", "alertes-solde"):
            for acteur in (self.homme, self.m_prod, self.dir_a):
                self.client.force_authenticate(user=acteur)
                self.assertEqual(self.get(chemin).status_code, 403, (chemin, acteur.username))
            self.client.force_authenticate(user=self.admin)
            self.assertEqual(self.get(chemin).status_code, 200, chemin)
            self.client.force_authenticate(user=None)
            self.assertEqual(self.get(chemin).status_code, 401, chemin)

    def test_annee_invalide(self):
        for chemin in ("employes-sans-conge-annuel", "alertes-solde"):
            self.assertEqual(self.get(chemin, annee="abc").status_code, 400)


class CongesSupprimesEtRenommesTests(BaseV2):
    def test_le_jeu_de_demonstration_n_a_plus_de_conge_sans_solde_ni_de_conge_paye(self):
        from django.core.management import call_command
        from conges.models import TypeConge

        TypeConge.objects.all().delete()
        call_command("seed_demo", verbosity=0)
        libelles = set(TypeConge.objects.values_list("libelle", flat=True))
        self.assertEqual(libelles, {"Congé annuel", "Congé maladie", "Congé de paternité", "Congé de maternité"})
        maternite = TypeConge.objects.get(libelle="Congé de maternité")
        self.assertTrue(maternite.est_maternite)
        self.assertTrue(maternite.decompte_solde)
