"""
Tests : date d'entrée obligatoire pour un employé, ancienneté, droit au congé
annuel (18 j/an dès un an d'ancienneté, sinon pas de solde donc pas de congé
annuel), indicateurs RH par département, export limité aux demandes validées.
"""
import csv
import io
from datetime import date, timedelta

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from accounts.models import RoleUtilisateur, Utilisateur
from conges.models import DemandeConge, NiveauValidation, SoldeConge, StatutDemande, Validation, DecisionValidation

from .test_evolutions_v2 import MEDIA_TMP, BaseV2, creer, jour


def il_y_a(jours):
    return timezone.localdate() - timedelta(days=jours)


def il_y_a_annees(n, decalage_jours=0):
    """Date située `n` années pleines avant aujourd'hui (+ décalage éventuel)."""
    t = timezone.localdate()
    try:
        d = t.replace(year=t.year - n)
    except ValueError:  # 29 février
        d = t.replace(year=t.year - n, day=28)
    return d + timedelta(days=decalage_jours)


def ouvre(n=10):
    """Décalage (en jours) du premier jour ouvré à partir d'aujourd'hui + n : évite les week-ends."""
    while (timezone.localdate() + timedelta(days=n)).weekday() >= 5:
        n += 1
    return n


def payload(**kw):
    base = {
        "username": "nouveau", "password": "Zx#9kLmN2026", "first_name": "No", "last_name": "Uveau",
        "email": "n@v.local", "matricule": "N1", "role": "EMPLOYE", "sexe": "F", "a_enfant": False,
        "date_embauche": str(il_y_a_annees(3)),
    }
    base.update(kw)
    return base


class AncienneteTests(BaseV2):
    def user(self, date_embauche):
        return Utilisateur(username="x", matricule="X", date_embauche=date_embauche)

    def test_annees_revolues(self):
        aujourdhui = date(2026, 10, 14)
        self.assertEqual(self.user(date(2023, 10, 14)).anciennete_annees(aujourdhui), 3)   # jour anniversaire
        self.assertEqual(self.user(date(2023, 10, 15)).anciennete_annees(aujourdhui), 2)   # veille de l'anniversaire
        self.assertEqual(self.user(date(2026, 1, 1)).anciennete_annees(aujourdhui), 0)
        self.assertEqual(self.user(date(2024, 2, 29)).anciennete_annees(date(2025, 2, 28)), 0)
        self.assertEqual(self.user(date(2024, 2, 29)).anciennete_annees(date(2025, 3, 1)), 1)

    def test_sans_date_pas_d_anciennete(self):
        self.assertIsNone(self.user(None).anciennete_annees())
        self.assertFalse(self.user(None).est_eligible_conge_annuel())

    def test_seuil_d_un_an(self):
        aujourdhui = date(2026, 10, 14)
        self.assertTrue(self.user(date(2025, 10, 14)).est_eligible_conge_annuel(aujourdhui))   # 1 an pile
        self.assertFalse(self.user(date(2025, 10, 15)).est_eligible_conge_annuel(aujourdhui))  # 364 jours


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class DateEntreeEtSoldeALaCreationTests(BaseV2):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)

    def solde_cp(self, user):
        return SoldeConge.objects.filter(
            utilisateur=user, type_conge=self.cp, annee=timezone.localdate().year
        ).first()

    def test_date_d_entree_obligatoire_pour_un_employe(self):
        sans = payload()
        del sans["date_embauche"]
        resp = self.client.post("/api/utilisateurs/", sans, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_embauche", resp.data)

    def test_date_d_entree_future_refusee(self):
        resp = self.client.post("/api/utilisateurs/", payload(date_embauche=str(jour(3))), format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_embauche", resp.data)

    def test_date_non_obligatoire_pour_les_autres_roles(self):
        sans = payload(role="RH", username="rh2", matricule="RH2")
        del sans["date_embauche"]
        self.assertEqual(self.client.post("/api/utilisateurs/", sans, format="json").status_code, 201)

    def test_plus_d_un_an_donne_18_jours_de_conge_annuel(self):
        resp = self.client.post("/api/utilisateurs/", payload(date_embauche=str(il_y_a_annees(3))), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["anciennete_annees"], 3)
        self.assertTrue(resp.data["eligible_conge_annuel"])
        solde = self.solde_cp(Utilisateur.objects.get(username="nouveau"))
        self.assertIsNotNone(solde)
        self.assertEqual((solde.jours_acquis, solde.jours_pris, solde.jours_restants), (18, 0, 18))

    def test_un_an_pile_donne_le_solde(self):
        self.client.post("/api/utilisateurs/", payload(date_embauche=str(il_y_a_annees(1))), format="json")
        self.assertIsNotNone(self.solde_cp(Utilisateur.objects.get(username="nouveau")))

    def test_moins_d_un_an_aucun_solde(self):
        resp = self.client.post("/api/utilisateurs/", payload(date_embauche=str(il_y_a(200))), format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["anciennete_annees"], 0)
        self.assertFalse(resp.data["eligible_conge_annuel"])
        self.assertIsNone(self.solde_cp(Utilisateur.objects.get(username="nouveau")))

    def test_jours_sans_plafond_18_par_defaut(self):
        self.cp.plafond_jours = None
        self.cp.save()
        self.client.post("/api/utilisateurs/", payload(), format="json")
        self.assertEqual(self.solde_cp(Utilisateur.objects.get(username="nouveau")).jours_acquis, 18)

    def test_les_types_non_decomptes_ne_creent_pas_de_solde(self):
        self.client.post("/api/utilisateurs/", payload(), format="json")
        user = Utilisateur.objects.get(username="nouveau")
        self.assertEqual(SoldeConge.objects.filter(utilisateur=user).count(), 1)  # congé annuel seulement

    def test_employe_sans_date_dans_l_annuaire_modifiable_sans_rapport(self):
        # Compte ancien sans date d'entrée : changer son téléphone n'est pas bloqué…
        self.assertEqual(
            self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"telephone": "670123456"}, format="json").status_code, 200
        )
        # …mais passer un manager en employé exige la date.
        resp = self.client.patch(f"/api/utilisateurs/{self.m_prod.pk}/", {"role": "EMPLOYE"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_embauche", resp.data)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class PasDeSoldePasDeCongeAnnuelTests(BaseV2):
    def setUp(self):
        super().setUp()
        self.recrue = creer("recrue", RoleUtilisateur.EMPLOYE, departement=self.prod, sexe="F",
                            date_embauche=il_y_a(120))
        self.ancien_sans_ligne = creer("ancien", RoleUtilisateur.EMPLOYE, departement=self.prod, sexe="M",
                                       date_embauche=il_y_a_annees(5))
        self.sans_date = creer("sans_date", RoleUtilisateur.EMPLOYE, departement=self.prod, sexe="M")

    def test_recrue_sans_solde_refusee_avec_explication(self):
        resp = self.demande(self.recrue, self.cp, debut=ouvre(), fin=ouvre())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("pas encore", str(resp.data["detail"]))
        self.assertIn("ancienneté", str(resp.data["detail"]))
        self.assertFalse(DemandeConge.objects.filter(utilisateur=self.recrue).exists())

    def test_sans_date_d_entree_refuse_avec_explication(self):
        resp = self.demande(self.sans_date, self.cp, debut=ouvre(), fin=ouvre())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date d'entrée", str(resp.data["detail"]))

    def test_autres_types_restent_ouverts_a_la_recrue(self):
        resp = self.demande(self.recrue, self.maladie, fichier=self.pdf(), debut=ouvre(), fin=ouvre())
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_employe_eligible_sans_ligne_de_solde_est_regularise_a_la_soumission(self):
        self.assertFalse(SoldeConge.objects.filter(utilisateur=self.ancien_sans_ligne).exists())
        resp = self.demande(self.ancien_sans_ligne, self.cp, debut=ouvre(), fin=ouvre())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            SoldeConge.objects.get(utilisateur=self.ancien_sans_ligne, type_conge=self.cp).jours_restants, 18
        )

    def test_solde_epuise_toujours_refuse(self):
        solde = SoldeConge.objects.get(utilisateur=self.homme, type_conge=self.cp)
        solde.jours_restants = 0
        solde.save()
        resp = self.demande(self.homme, self.cp, debut=ouvre(), fin=ouvre())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("insuffisant", str(resp.data["detail"]))

    def test_consulter_son_profil_cree_le_solde_au_premier_anniversaire(self):
        pile_un_an = creer("anniv", RoleUtilisateur.EMPLOYE, sexe="F", date_embauche=il_y_a_annees(1))
        self.assertFalse(SoldeConge.objects.filter(utilisateur=pile_un_an).exists())
        self.client.force_authenticate(user=pile_un_an)
        data = self.client.get("/api/me/").data
        self.assertEqual([(s["type_conge_libelle"], s["jours_restants"]) for s in data["soldes"]], [("Congé annuel", 18.0)])
        self.assertTrue(data["profil"]["eligible_conge_annuel"])

    def test_consulter_son_profil_n_invente_pas_de_solde_a_la_recrue(self):
        self.client.force_authenticate(user=self.recrue)
        self.assertEqual(self.client.get("/api/me/").data["soldes"], [])

    def test_commande_de_regularisation(self):
        call_command("synchroniser_soldes", verbosity=0)
        self.assertTrue(SoldeConge.objects.filter(utilisateur=self.ancien_sans_ligne, type_conge=self.cp).exists())
        self.assertFalse(SoldeConge.objects.filter(utilisateur=self.recrue).exists())
        self.assertFalse(SoldeConge.objects.filter(utilisateur=self.sans_date).exists())
        avant = SoldeConge.objects.count()
        call_command("synchroniser_soldes", verbosity=0)  # idempotent
        self.assertEqual(SoldeConge.objects.count(), avant)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class CorrectionDeLaDateDEntreeTests(BaseV2):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)
        self.client.post("/api/utilisateurs/", payload(), format="json")
        self.user = Utilisateur.objects.get(username="nouveau")

    def solde(self):
        return SoldeConge.objects.filter(utilisateur=self.user, type_conge=self.cp).first()

    def test_reculer_la_date_d_entree_retire_le_solde_intact(self):
        self.assertIsNotNone(self.solde())
        self.client.patch(f"/api/utilisateurs/{self.user.pk}/", {"date_embauche": str(il_y_a(30))}, format="json")
        self.assertIsNone(self.solde())

    def test_un_solde_entame_n_est_jamais_retire(self):
        s = self.solde()
        s.jours_pris, s.jours_restants = 3, 15
        s.save()
        self.client.patch(f"/api/utilisateurs/{self.user.pk}/", {"date_embauche": str(il_y_a(30))}, format="json")
        self.assertEqual(self.solde().jours_restants, 15)

    def test_avancer_la_date_d_entree_cree_le_solde(self):
        self.client.patch(f"/api/utilisateurs/{self.user.pk}/", {"date_embauche": str(il_y_a(30))}, format="json")
        self.assertIsNone(self.solde())
        self.client.patch(f"/api/utilisateurs/{self.user.pk}/", {"date_embauche": str(il_y_a_annees(2))}, format="json")
        self.assertEqual(self.solde().jours_restants, 18)

    def test_date_effacee_refusee_pour_un_employe(self):
        resp = self.client.patch(f"/api/utilisateurs/{self.user.pk}/", {"date_embauche": None}, format="json")
        self.assertEqual(resp.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class IndicateursRHParDepartementTests(BaseV2):
    def setUp(self):
        super().setUp()
        # Production : homme (ancien), femme (recrue) ; Comptabilité : emp_compta (ancien) ; Logistique : emp_logi (ancien)
        self.homme.date_embauche = il_y_a_annees(3)
        self.femme.date_embauche = il_y_a(100)
        self.emp_compta.date_embauche = il_y_a_annees(2)
        self.emp_logi.date_embauche = il_y_a_annees(4)
        for u in (self.homme, self.femme, self.emp_compta, self.emp_logi):
            u.save()
        self.annee = timezone.localdate().year
        DemandeConge.objects.create(
            utilisateur=self.homme, type_conge=self.cp, date_debut=jour(10), date_fin=jour(12),
            nb_jours_ouvres=3, statut=StatutDemande.VALIDEE,
        )
        DemandeConge.objects.create(  # non validée : ne compte pas
            utilisateur=self.femme, type_conge=self.maladie, date_debut=jour(10), date_fin=jour(12),
            nb_jours_ouvres=3, statut=StatutDemande.EN_ATTENTE_MANAGER,
        )
        self.client.force_authenticate(user=self.rh)

    def lignes(self):
        data = self.client.get("/api/dashboard/rh/", {"annee": jour(10).year}).data
        return {l["departement"]: l for l in data["par_departement"]}, data

    def test_effectif_eligibles_et_ont_pris_conge_par_departement(self):
        lignes, _ = self.lignes()
        prod = lignes["Production"]
        self.assertEqual(prod["effectif"], 3)            # manager + 2 employés
        self.assertEqual(prod["employes"], 2)
        self.assertEqual(prod["eligibles_conge_annuel"], 1)  # homme seulement (femme < 1 an)
        self.assertEqual(prod["ont_pris_conge"], 1)       # homme (congé validé) ; la demande en attente de femme ne compte pas
        self.assertEqual(prod["jours_conges_valides"], 3)
        self.assertEqual(lignes["Comptabilité"]["employes"], 1)
        self.assertEqual(lignes["Comptabilité"]["eligibles_conge_annuel"], 1)
        self.assertEqual(lignes["Comptabilité"]["ont_pris_conge"], 0)
        self.assertEqual(lignes["Logistique"]["effectif"], 1)
        self.assertEqual(lignes["Logistique"]["eligibles_conge_annuel"], 1)

    def test_comptes_actifs_sans_departement_comptes_a_part(self):
        lignes, _ = self.lignes()
        self.assertEqual(lignes["Sans département"]["effectif"], 4)  # dir_a, dir_b, rh, admin
        self.assertEqual(lignes["Sans département"]["employes"], 0)

    def test_totaux_coherents(self):
        lignes, data = self.lignes()
        for champ in ("effectif", "employes", "eligibles_conge_annuel", "ont_pris_conge", "jours_conges_valides"):
            self.assertEqual(data["totaux"][champ], sum(l[champ] for l in lignes.values()), champ)

    def test_utilisateurs_desactives_ignores(self):
        self.homme.actif = False
        self.homme.save()
        lignes, _ = self.lignes()
        self.assertEqual(lignes["Production"]["employes"], 1)
        self.assertEqual(lignes["Production"]["eligibles_conge_annuel"], 0)
        self.assertEqual(lignes["Production"]["ont_pris_conge"], 0)

    def test_sans_conge_annuel_ne_compte_que_les_eligibles_sans_conge_annuel_valide_cette_annee(self):
        # femme (recrue, non éligible) : congé annuel validé l'an dernier + demande refusée cette année.
        DemandeConge.objects.create(
            utilisateur=self.femme, type_conge=self.cp, date_debut=date(self.annee - 1, 6, 1),
            date_fin=date(self.annee - 1, 6, 2), nb_jours_ouvres=2, statut=StatutDemande.VALIDEE,
        )
        # emp_compta : seulement un congé maladie validé (pas un congé annuel) -> reste « sans congé annuel ».
        DemandeConge.objects.create(
            utilisateur=self.emp_compta, type_conge=self.maladie, date_debut=jour(10), date_fin=jour(11),
            nb_jours_ouvres=2, statut=StatutDemande.VALIDEE,
        )
        data = self.client.get("/api/dashboard/rh/", {"annee": jour(10).year}).data
        # éligibles : homme (a un congé annuel validé -> exclu), emp_compta, emp_logi ; femme non éligible.
        self.assertEqual(data["salaries_sans_conge_annuel"], 2)

    def test_acces_reserve_rh_et_admin(self):
        for acteur in (self.homme, self.m_prod, self.dir_a):
            self.client.force_authenticate(user=acteur)
            self.assertEqual(self.client.get("/api/dashboard/rh/").status_code, 403, acteur.username)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get("/api/dashboard/rh/").status_code, 200)

    def test_annee_invalide(self):
        self.assertEqual(self.client.get("/api/dashboard/rh/", {"annee": "abc"}).status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class ExportValideesUniquementTests(BaseV2):
    def creer_demande(self, user, statut, debut, fin=None, type_conge=None):
        d = DemandeConge.objects.create(
            utilisateur=user, type_conge=type_conge or self.cp, date_debut=jour(debut), date_fin=jour(fin or debut + 1),
            nb_jours_ouvres=2, statut=statut,
        )
        return d

    def setUp(self):
        super().setUp()
        for u, mat in ((self.homme, "MAT-VALIDE"), (self.femme, "MAT-ATTENTE"), (self.emp_compta, "MAT-REFUSE"),
                       (self.emp_logi, "MAT-ANNULE")):
            u.matricule = mat
            u.save()
        valide = self.creer_demande(self.homme, StatutDemande.VALIDEE, 10)
        Validation.objects.create(demande=valide, niveau=NiveauValidation.MANAGER,
                                  decision=DecisionValidation.APPROUVE, auteur=self.m_prod)
        Validation.objects.create(demande=valide, niveau=NiveauValidation.DIRECTION,
                                  decision=DecisionValidation.APPROUVE, auteur=self.dir_a)
        self.creer_demande(self.femme, StatutDemande.EN_ATTENTE_MANAGER, 20)
        self.creer_demande(self.femme, StatutDemande.EN_ATTENTE_DIRECTION, 30)
        self.creer_demande(self.emp_compta, StatutDemande.REFUSEE, 12)
        self.creer_demande(self.emp_logi, StatutDemande.ANNULEE, 14)
        self.creer_demande(self.emp_logi, StatutDemande.BROUILLON, 16)
        self.client.force_authenticate(user=self.rh)

    def test_csv_ne_contient_que_les_demandes_validees(self):
        resp = self.client.get("/api/export/demandes.csv")
        self.assertEqual(resp.status_code, 200)
        texte = resp.content.decode("utf-8")
        self.assertIn("MAT-VALIDE", texte)
        for exclu in ("MAT-ATTENTE", "MAT-REFUSE", "MAT-ANNULE"):
            self.assertNotIn(exclu, texte)
        self.assertEqual(len(texte.strip().splitlines()), 2)  # en-tête + 1 demande
        self.assertTrue(texte.startswith("﻿"))  # BOM pour Excel

    def lignes_csv(self, **params):
        resp = self.client.get("/api/export/demandes.csv", params)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("demandes_conges_validees", resp["Content-Disposition"])
        return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))

    def test_contenu_du_csv(self):
        lignes = self.lignes_csv()
        self.assertEqual(lignes[0][:3], ["Employé", "Matricule", "Département"])
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1][1], "MAT-VALIDE")
        self.assertEqual(lignes[1][2], "Production")
        self.assertEqual(lignes[1][3], "Congé annuel")
        self.assertEqual(lignes[1][6], "2")
        self.assertEqual(lignes[1][4], str(jour(10)))
        self.assertEqual(lignes[1][7], str(timezone.localdate()))  # validée le (décision de la Direction)

    def test_filtre_par_annee(self):
        self.assertEqual(len(self.lignes_csv(annee=jour(10).year)), 2)
        self.assertEqual(len(self.lignes_csv(annee=jour(10).year - 5)), 1)  # en-tête seul

    def test_filtre_par_mois_et_annee(self):
        d = jour(10)
        self.assertEqual(len(self.lignes_csv(annee=d.year, mois=d.month)), 2)
        autre_mois = d.month % 12 + 1
        self.assertEqual(len(self.lignes_csv(annee=d.year, mois=autre_mois)), 1)
        self.assertEqual(len(self.lignes_csv(mois=d.month)), 2)  # mois seul : toutes années
        self.assertEqual(len(self.lignes_csv(annee="", mois="")), 2)  # vides = pas de filtre
        resp = self.client.get("/api/export/demandes.csv", {"annee": d.year, "mois": d.month})
        self.assertIn(f"demandes_conges_validees_{d.year}_{d.month:02d}.csv", resp["Content-Disposition"])

    def test_mois_ou_annee_invalide_renvoie_400(self):
        for params in ({"mois": 13}, {"mois": 0}, {"mois": "abc"}, {"annee": "xx"}):
            self.assertEqual(self.client.get("/api/export/demandes.csv", params).status_code, 400, params)

    def test_export_vide_si_aucune_demande_validee(self):
        DemandeConge.objects.filter(statut=StatutDemande.VALIDEE).update(statut=StatutDemande.REFUSEE)
        self.assertEqual(len(self.lignes_csv()), 1)

    def test_plus_d_export_excel(self):
        self.assertEqual(self.client.get("/api/export/demandes.xlsx").status_code, 404)

    def test_acces_reserve_rh_et_admin(self):
        route = "/api/export/demandes.csv"
        for acteur in (self.homme, self.m_prod, self.dir_a):
            self.client.force_authenticate(user=acteur)
            self.assertEqual(self.client.get(route).status_code, 403, acteur.username)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(route).status_code, 200)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(route).status_code, 401)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class AccesALaDemandeDepuisUneNotificationTests(BaseV2):
    """Le Manager et le Directeur arrivent sur la demande via la notification
    reçue : l'API doit leur donner ce détail (et à eux seuls)."""

    def test_manager_et_directeur_recoivent_une_notification_qui_pointe_sur_la_demande(self):
        demande_id = self.demande(self.homme, self.cp, debut=20, fin=21).data["id"]

        self.client.force_authenticate(user=self.m_prod)
        notif = self.client.get("/api/notifications/").data["results"][0]
        self.assertEqual(notif["demande"], demande_id)
        detail = self.client.get(f"/api/demandes/{notif['demande']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["statut"], StatutDemande.EN_ATTENTE_MANAGER)

        self.client.post(f"/api/demandes/{demande_id}/valider-manager/", {"decision": "APPROUVE"}, format="json")
        self.client.force_authenticate(user=self.dir_a)
        notif = self.client.get("/api/notifications/").data["results"][0]
        self.assertEqual(notif["demande"], demande_id)
        detail = self.client.get(f"/api/demandes/{notif['demande']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["statut"], StatutDemande.EN_ATTENTE_DIRECTION)

    def test_un_directeur_hors_perimetre_n_a_pas_acces_a_la_demande(self):
        demande_id = self.demande(self.homme, self.cp, debut=20, fin=21).data["id"]
        self.client.force_authenticate(user=self.dir_b)  # ne supervise pas Production
        self.assertEqual(self.client.get(f"/api/demandes/{demande_id}/").status_code, 404)
