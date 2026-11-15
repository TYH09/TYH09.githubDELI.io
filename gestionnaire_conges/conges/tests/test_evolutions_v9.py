"""
Tests : demandes de congé du RH, du chef de département et du directeur
(validation à 1 niveau), mêmes règles de droit que les employés, et format
du matricule (majuscules, chiffres, 8 à 16 caractères).
"""
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Departement, FonctionDirection, RoleUtilisateur, Utilisateur
from conges.models import JourFerie, Notification, SoldeConge, StatutDemande, TypeConge

MDP = "Pass#1234"


def jour_ouvre(n):
    d = timezone.localdate() + timedelta(days=n)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def creer(username, role, **kw):
    kw.setdefault("matricule", username.upper() + "00001")
    kw.setdefault("date_embauche", date(2018, 1, 1))
    kw.setdefault("sexe", "M")
    return Utilisateur.objects.create_user(username=username, password=MDP, role=role, **kw)


class Base(APITestCase):
    def setUp(self):
        TypeConge.objects.all().delete()
        JourFerie.objects.all().delete()
        self.cp = TypeConge.objects.create(
            libelle="Congé annuel", plafond_jours=18, decompte_solde=True, est_conge_annuel=True,
            delai_minimum_jours=0,
        )
        self.prod = Departement.objects.create(nom="Production")
        self.compta = Departement.objects.create(nom="Comptabilité")
        self.daf = creer("daf", RoleUtilisateur.DIRECTEUR, fonction_direction=FonctionDirection.DAF)
        self.dga = creer("dga", RoleUtilisateur.DIRECTEUR, fonction_direction=FonctionDirection.DGA)
        self.dg = creer("dg", RoleUtilisateur.DIRECTEUR, fonction_direction=FonctionDirection.DG)
        self.rh = creer("rh", RoleUtilisateur.RH)
        self.chef = creer("chef", RoleUtilisateur.MANAGER, departement=self.prod)
        self.prod.responsable = self.chef
        self.prod.directeur = self.dga
        self.prod.save()
        self.compta.directeur = self.dg
        self.compta.save()
        self.employe = creer("emp", RoleUtilisateur.EMPLOYE, departement=self.prod)
        self.admin = creer("adm", RoleUtilisateur.ADMINISTRATEUR)
        for u in (self.daf, self.dga, self.dg, self.rh, self.chef, self.employe):
            u.refresh_from_db()
            from conges.droits import synchroniser_soldes
            synchroniser_soldes(u)

    def demander(self, user, **extra):
        self.client.force_authenticate(user=user)
        debut = jour_ouvre(10)
        return self.client.post("/api/demandes/", {
            "type_conge": self.cp.pk, "date_debut": str(debut), "date_fin": str(debut), **extra,
        }, format="json")

    def agir(self, user, demande_id, action, decision="APPROUVE"):
        self.client.force_authenticate(user=user)
        return self.client.post(f"/api/demandes/{demande_id}/{action}/", {"decision": decision}, format="json")

    def solde(self, user):
        return SoldeConge.objects.get(utilisateur=user, type_conge=self.cp, annee=timezone.localdate().year)


class DemandeDuRHTests(Base):
    def test_la_demande_du_rh_attend_le_daf(self):
        r = self.demander(self.rh)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["statut"], StatutDemande.EN_ATTENTE_DIRECTION)
        self.assertTrue(Notification.objects.filter(utilisateur=self.daf, demande_id=r.data["id"]).exists())
        self.assertFalse(Notification.objects.filter(utilisateur=self.dga, demande_id=r.data["id"]).exists())

    def test_seul_le_daf_la_voit_et_la_valide(self):
        did = self.demander(self.rh).data["id"]
        for autre in (self.dga, self.dg):
            self.client.force_authenticate(user=autre)
            self.assertEqual(self.client.get(f"/api/demandes/{did}/").status_code, 404)
            self.assertEqual(self.agir(autre, did, "valider-direction").status_code, 404)
        r = self.agir(self.daf, did, "valider-direction")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["statut"], StatutDemande.VALIDEE)
        self.assertEqual(self.solde(self.rh).jours_restants, 17)

    def test_sans_daf_toute_la_direction_peut_statuer(self):
        Utilisateur.objects.filter(pk=self.daf.pk).update(actif=False)
        did = self.demander(self.rh).data["id"]
        self.assertEqual(self.agir(self.dga, did, "valider-direction").status_code, 200)

    def test_le_rh_ne_peut_pas_valider_sa_propre_demande(self):
        did = self.demander(self.rh).data["id"]
        self.assertEqual(self.agir(self.rh, did, "valider-rh").status_code, 403)
        self.assertEqual(self.agir(self.rh, did, "valider-direction").status_code, 403)

    def test_refus_du_daf(self):
        did = self.demander(self.rh).data["id"]
        r = self.agir(self.daf, did, "valider-direction", "REFUSE")
        self.assertEqual(r.data["statut"], StatutDemande.REFUSEE)
        self.assertEqual(self.solde(self.rh).jours_restants, 18)


class DemandeDuChefTests(Base):
    def test_la_demande_du_chef_attend_son_directeur(self):
        r = self.demander(self.chef)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["statut"], StatutDemande.EN_ATTENTE_DIRECTION)
        did = r.data["id"]
        self.assertTrue(Notification.objects.filter(utilisateur=self.dga, demande_id=did).exists())
        self.assertFalse(Notification.objects.filter(utilisateur=self.chef, message__contains="à valider").exists())

    def test_seul_le_directeur_designe_statue(self):
        did = self.demander(self.chef).data["id"]
        for autre in (self.dg, self.daf):
            self.client.force_authenticate(user=autre)
            self.assertEqual(self.client.get(f"/api/demandes/{did}/").status_code, 404)
        self.assertEqual(self.agir(self.chef, did, "valider-manager").status_code, 403)
        r = self.agir(self.dga, did, "valider-direction")
        self.assertEqual(r.data["statut"], StatutDemande.VALIDEE)
        self.assertEqual(self.solde(self.chef).jours_restants, 17)

    def test_le_chef_voit_sa_demande_mais_pas_celle_d_un_autre_chef(self):
        did = self.demander(self.chef).data["id"]
        self.client.force_authenticate(user=self.chef)
        self.assertEqual(self.client.get(f"/api/demandes/{did}/").status_code, 200)

    def test_la_demande_d_un_employe_garde_ses_deux_niveaux(self):
        r = self.demander(self.employe)
        self.assertEqual(r.data["statut"], StatutDemande.EN_ATTENTE_MANAGER)
        did = r.data["id"]
        self.assertEqual(self.agir(self.chef, did, "valider-manager").data["statut"], StatutDemande.EN_ATTENTE_DIRECTION)
        self.assertEqual(self.agir(self.dga, did, "valider-direction").data["statut"], StatutDemande.VALIDEE)

    def test_le_directeur_ne_voit_pas_les_employes_d_un_autre_departement(self):
        did = self.demander(self.employe).data["id"]
        self.client.force_authenticate(user=self.dg)
        self.assertEqual(self.client.get(f"/api/demandes/{did}/").status_code, 404)


class DemandeDuDirecteurTests(Base):
    def test_la_demande_du_directeur_attend_le_rh(self):
        r = self.demander(self.dga)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["statut"], StatutDemande.EN_ATTENTE_RH)
        self.assertTrue(Notification.objects.filter(utilisateur=self.rh, demande_id=r.data["id"]).exists())

    def test_le_rh_la_valide(self):
        did = self.demander(self.dga).data["id"]
        r = self.agir(self.rh, did, "valider-rh")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["statut"], StatutDemande.VALIDEE)
        self.assertEqual(r.data["validations"][0]["niveau"], "RH")
        self.assertEqual(self.solde(self.dga).jours_restants, 17)

    def test_un_directeur_ne_valide_pas_la_demande_d_un_autre_directeur(self):
        did = self.demander(self.dga).data["id"]
        for autre in (self.dg, self.daf, self.dga):
            self.client.force_authenticate(user=autre)
            self.assertIn(self.agir(autre, did, "valider-direction").status_code, (400, 403, 404))
        self.client.force_authenticate(user=self.dg)
        self.assertEqual(self.client.get(f"/api/demandes/{did}/").status_code, 404)

    def test_valider_rh_reserve_aux_demandes_de_directeur(self):
        did = self.demander(self.chef).data["id"]
        self.assertEqual(self.agir(self.rh, did, "valider-rh").status_code, 403)

    def test_refus_du_rh(self):
        did = self.demander(self.dga).data["id"]
        r = self.agir(self.rh, did, "valider-rh", "REFUSE")
        self.assertEqual(r.data["statut"], StatutDemande.REFUSEE)
        self.assertEqual(self.solde(self.dga).jours_restants, 18)

    def test_l_administrateur_ne_demande_pas_de_conge(self):
        self.assertEqual(self.demander(self.admin).status_code, 403)


class MemesReglesQueLesEmployesTests(Base):
    def test_moins_d_un_an_aucun_solde_annuel(self):
        for role in (RoleUtilisateur.RH, RoleUtilisateur.MANAGER, RoleUtilisateur.DIRECTEUR):
            u = creer(f"nouv{role.lower()}", role, date_embauche=timezone.localdate() - timedelta(days=100),
                      fonction_direction=FonctionDirection.DG if role == RoleUtilisateur.DIRECTEUR else None)
            self.assertFalse(SoldeConge.objects.filter(utilisateur=u).exists(), role)
            r = self.demander(u)
            self.assertEqual(r.status_code, 400, role)

    def test_une_femme_avec_enfant_de_moins_de_6_ans_a_21_jours(self):
        for role in (RoleUtilisateur.RH, RoleUtilisateur.MANAGER, RoleUtilisateur.DIRECTEUR):
            u = creer(f"mere{role.lower()}", role, sexe="F", a_enfant=True, age_dernier_enfant=3,
                      fonction_direction=FonctionDirection.DG if role == RoleUtilisateur.DIRECTEUR else None)
            from conges.droits import synchroniser_soldes
            synchroniser_soldes(u)
            self.assertEqual(self.solde(u).jours_acquis, 21, role)

    def test_creation_de_compte_exige_les_champs_pour_ces_roles(self):
        self.client.force_authenticate(user=self.admin)
        base = {
            "username": "nvl", "password": "Zx9#kLm!2026", "first_name": "N", "last_name": "V",
            "matricule": "NOUVELLE01", "sexe": "F", "role": "RH",
        }
        r = self.client.post("/api/utilisateurs/", base, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_embauche", r.data)
        r = self.client.post("/api/utilisateurs/", {**base, "date_embauche": "2019-01-01"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("a_enfant", r.data)
        r = self.client.post(
            "/api/utilisateurs/", {**base, "date_embauche": "2019-01-01", "a_enfant": True, "age_dernier_enfant": 2},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["droit_conge_annuel"], 21)


class MatriculeTests(Base):
    def creer_compte(self, matricule, **extra):
        self.client.force_authenticate(user=self.admin)
        return self.client.post("/api/utilisateurs/", {
            "username": f"u{abs(hash(str(matricule))) % 10**6}", "password": "Zx9#kLm!2026", "first_name": "A",
            "last_name": "B", "matricule": matricule, "sexe": "M", "role": "EMPLOYE",
            "date_embauche": "2019-01-01", **extra,
        }, format="json")

    def test_mise_en_majuscules_automatique(self):
        r = self.creer_compte("  abc12345 ")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["matricule"], "ABC12345")

    def test_limites_de_longueur(self):
        self.assertEqual(self.creer_compte("ABC1234").status_code, 400)       # 7
        self.assertEqual(self.creer_compte("ABC12345").status_code, 201)      # 8
        self.assertEqual(self.creer_compte("ABCDEFGH12345678").status_code, 201)  # 16
        self.assertEqual(self.creer_compte("ABCDEFGH123456789").status_code, 400)  # 17

    def test_doit_contenir_un_chiffre(self):
        r = self.creer_compte("ABCDEFGHIJ")
        self.assertEqual(r.status_code, 400)
        self.assertIn("chiffre", str(r.data["matricule"]))

    def test_caracteres_speciaux_refuses(self):
        for m in ("ABC-12345", "ABC 12345", "ÉTÉ123456", "ABC_12345"):
            self.assertEqual(self.creer_compte(m).status_code, 400, m)

    def test_unicite_sans_tenir_compte_de_la_casse(self):
        self.assertEqual(self.creer_compte("UNIQUE001").status_code, 201)
        self.assertEqual(self.creer_compte("unique001").status_code, 400)

    def test_un_ancien_matricule_n_est_pas_bloque_tant_qu_il_n_est_pas_modifie(self):
        Utilisateur.objects.filter(pk=self.employe.pk).update(matricule="E1")
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(f"/api/utilisateurs/{self.employe.pk}/", {"first_name": "Zoé", "matricule": "E1"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.client.patch(f"/api/utilisateurs/{self.employe.pk}/", {"matricule": "E2"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f"/api/utilisateurs/{self.employe.pk}/", {"matricule": "e2345678"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.employe.refresh_from_db()
        self.assertEqual(self.employe.matricule, "E2345678")


class PaterniteTests(Base):
    def setUp(self):
        super().setUp()
        self.pat = TypeConge.objects.create(
            libelle="Congé de paternité", plafond_jours=3, decompte_solde=False, reserve_a_sexe="M",
            justificatif_obligatoire=False, delai_minimum_jours=0,
        )

    def demander_pat(self, user, debut, **extra):
        self.client.force_authenticate(user=user)
        return self.client.post("/api/demandes/", {"type_conge": self.pat.pk, "date_debut": str(debut), **extra}, format="json")

    def lundi(self):
        d = timezone.localdate() + timedelta(days=14)
        return d + timedelta(days=(7 - d.weekday()) % 7)

    def test_date_de_fin_calculee_3_jours_ouvres(self):
        debut = self.lundi()
        r = self.demander_pat(self.employe, debut)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["date_fin"], str(debut + timedelta(days=2)))
        self.assertEqual(r.data["nb_jours_ouvres"], 3)
        self.assertEqual(r.data["date_retour"], str(debut + timedelta(days=3)))

    def test_la_date_de_fin_saisie_est_ignoree(self):
        debut = self.lundi()
        r = self.demander_pat(self.employe, debut, date_fin=str(debut + timedelta(days=10)))
        self.assertEqual(r.data["date_fin"], str(debut + timedelta(days=2)))
        self.assertEqual(r.data["nb_jours_ouvres"], 3)

    def test_les_weekends_et_feries_ne_comptent_pas(self):
        debut = self.lundi() + timedelta(days=3)  # jeudi : jeu, ven, puis lundi suivant
        JourFerie.objects.create(date=debut + timedelta(days=4), libelle="Férié test", recurrent=False)  # lundi
        r = self.demander_pat(self.employe, debut)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["date_fin"], str(debut + timedelta(days=5)))  # mardi
        self.assertEqual(r.data["nb_jours_ouvres"], 3)

    def test_depart_un_samedi(self):
        samedi = self.lundi() + timedelta(days=5)
        r = self.demander_pat(self.employe, samedi)
        self.assertEqual(r.data["date_fin"], str(samedi + timedelta(days=4)))  # mer
        self.assertEqual(r.data["nb_jours_ouvres"], 3)

    def test_jamais_plus_de_3_jours_ouvres(self):
        from conges.models import DemandeConge, RegleMetierError
        d = DemandeConge(utilisateur=self.employe, type_conge=self.pat, date_debut=self.lundi(),
                         date_fin=self.lundi() + timedelta(days=4))
        with self.assertRaises(RegleMetierError):
            d.verifier_regles_metier()

    def test_reserve_aux_hommes(self):
        femme = creer("femme", RoleUtilisateur.EMPLOYE, sexe="F", a_enfant=False, departement=self.prod)
        self.assertEqual(self.demander_pat(femme, self.lundi()).status_code, 400)
