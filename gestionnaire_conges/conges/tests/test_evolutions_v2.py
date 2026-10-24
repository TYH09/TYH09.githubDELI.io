"""
Tests des évolutions : sexe + congés réservés (maternité/paternité), édition
complète des comptes par l'Administrateur, justificatifs visibles aux deux
niveaux de validation (et à eux seuls), directeur multi-départements.
"""
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Departement, FonctionDirection, RoleUtilisateur, Utilisateur
from conges.models import JournalAudit, Notification, SoldeConge, TypeConge

MDP = "Pass#1234"
PDF = b"%PDF-1.4\n%contenu de test\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
MEDIA_TMP = tempfile.mkdtemp(prefix="media_tests_")


def jour(n):
    return timezone.localdate() + timedelta(days=n)


def creer(username, role, **kw):
    kw.setdefault("matricule", username.upper())
    return Utilisateur.objects.create_user(username=username, password=MDP, role=role, **kw)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class BaseV2(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        self.prod = Departement.objects.create(nom="Production")
        self.compta = Departement.objects.create(nom="Comptabilité")
        self.logistique = Departement.objects.create(nom="Logistique")

        self.m_prod = creer("m_prod", RoleUtilisateur.MANAGER, departement=self.prod, sexe="F")
        self.prod.responsable = self.m_prod
        self.prod.save()
        self.m_compta = creer("m_compta", RoleUtilisateur.MANAGER, departement=self.compta, sexe="M")
        self.compta.responsable = self.m_compta
        self.compta.save()

        self.dir_a = creer("dir_a", RoleUtilisateur.DIRECTEUR, fonction_direction=FonctionDirection.DAF, sexe="M")
        self.dir_b = creer("dir_b", RoleUtilisateur.DIRECTEUR, fonction_direction=FonctionDirection.DU, sexe="F")
        # dir_a supervise Production ET Comptabilité ; Logistique n'a pas de directeur
        self.prod.directeur = self.dir_a
        self.prod.save()
        self.compta.directeur = self.dir_a
        self.compta.save()

        self.rh = creer("rh", RoleUtilisateur.RH, sexe="F")
        self.admin = creer("admin", RoleUtilisateur.ADMINISTRATEUR, sexe="M")

        self.homme = creer("homme", RoleUtilisateur.EMPLOYE, departement=self.prod, sexe="M")
        self.femme = creer("femme", RoleUtilisateur.EMPLOYE, departement=self.prod, sexe="F")
        self.emp_compta = creer("emp_compta", RoleUtilisateur.EMPLOYE, departement=self.compta, sexe="F")
        self.emp_logi = creer("emp_logi", RoleUtilisateur.EMPLOYE, departement=self.logistique, sexe="M")

        self.cp = TypeConge.objects.create(libelle="Congé annuel", plafond_jours=18, decompte_solde=True)
        self.mat = TypeConge.objects.create(
            libelle="Congé de maternité", plafond_jours=90, decompte_solde=False,
            justificatif_obligatoire=True, reserve_a_sexe="F",
        )
        self.pat = TypeConge.objects.create(
            libelle="Congé de paternité", plafond_jours=3, decompte_solde=False,
            justificatif_obligatoire=True, reserve_a_sexe="M",
        )
        self.maladie = TypeConge.objects.create(
            libelle="Congé maladie", decompte_solde=False, justificatif_obligatoire=True,
        )
        for u in (self.homme, self.femme, self.emp_compta, self.emp_logi):
            SoldeConge.objects.create(
                utilisateur=u, type_conge=self.cp, annee=timezone.now().year,
                jours_acquis=18, jours_restants=18,
            )

    def demande(self, user, type_conge, fichier=None, debut=10, fin=11):
        self.client.force_authenticate(user=user)
        data = {
            "type_conge": type_conge.pk,
            "date_debut": jour(debut).isoformat(), "date_fin": jour(fin).isoformat(),
        }
        if fichier is not None:
            data["justificatif_fichier"] = fichier
        return self.client.post("/api/demandes/", data, format="multipart")

    @staticmethod
    def pdf(nom="certificat.pdf", contenu=PDF):
        return SimpleUploadedFile(nom, contenu, content_type="application/pdf")


# ---------------------------------------------------------------------------
class SexeEtCongesReservesTests(BaseV2):
    def _payload(self, **extra):
        data = {
            "username": "nouveau", "password": "Zx9#kLm!2026", "first_name": "N", "last_name": "V",
            "email": "n@v.local", "matricule": "N1", "role": "EMPLOYE", "sexe": "F", "a_enfant": False,
            "date_embauche": "2020-01-15",
        }
        data.update(extra)
        return data

    def test_creation_compte_avec_sexe(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/utilisateurs/", self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["sexe"], "F")
        self.assertEqual(Utilisateur.objects.get(username="nouveau").sexe, "F")

    def test_sexe_obligatoire_et_valide_a_la_creation(self):
        self.client.force_authenticate(user=self.admin)
        sans = self._payload()
        del sans["sexe"]
        self.assertEqual(self.client.post("/api/utilisateurs/", sans, format="json").status_code, 400)
        self.assertEqual(
            self.client.post("/api/utilisateurs/", self._payload(sexe="X"), format="json").status_code, 400
        )

    def test_homme_ne_peut_pas_prendre_la_maternite(self):
        resp = self.demande(self.homme, self.mat, self.pdf())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("réservé aux femmes", str(resp.data["detail"]))

    def test_femme_ne_peut_pas_prendre_la_paternite(self):
        resp = self.demande(self.femme, self.pat, self.pdf())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("réservé aux hommes", str(resp.data["detail"]))

    def test_femme_maternite_et_homme_paternite_acceptes(self):
        self.assertEqual(self.demande(self.femme, self.mat, self.pdf()).status_code, 201)
        self.assertEqual(self.demande(self.homme, self.pat, self.pdf()).status_code, 201)

    def test_types_non_reserves_ouverts_aux_deux_sexes(self):
        self.assertEqual(self.demande(self.homme, self.cp, debut=20, fin=21).status_code, 201)
        self.assertEqual(self.demande(self.femme, self.cp, debut=20, fin=21).status_code, 201)
        self.assertEqual(self.demande(self.homme, self.maladie, self.pdf(), debut=30, fin=31).status_code, 201)

    def test_sexe_non_renseigne_bloque_les_types_reserves(self):
        Utilisateur.objects.filter(pk=self.homme.pk).update(sexe=None)
        self.homme.refresh_from_db()
        resp = self.demande(self.homme, self.pat, self.pdf())
        self.assertEqual(resp.status_code, 400)
        self.assertIn("sexe", str(resp.data["detail"]))
        # un type ordinaire reste accessible
        self.assertEqual(self.demande(self.homme, self.cp, debut=20, fin=21).status_code, 201)

    def test_rh_peut_reserver_un_type_a_un_sexe(self):
        self.client.force_authenticate(user=self.rh)
        resp = self.client.post(
            "/api/types-conge/", {"libelle": "Congé allaitement", "reserve_a_sexe": "F"}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["reserve_a_sexe"], "F")


# ---------------------------------------------------------------------------
class EditionComptesParAdminTests(BaseV2):
    def test_admin_modifie_toutes_les_informations(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/utilisateurs/{self.femme.pk}/", {
            "first_name": "Marie", "last_name": "Nkou", "username": "m.nkou",
            "email": "marie@delifood.local", "matricule": "MAT-77", "sexe": "F",
            "role": "MANAGER", "departement": self.compta.pk, "password": "Nouveau#Mdp2026",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.femme.refresh_from_db()
        self.assertEqual(
            (self.femme.first_name, self.femme.last_name, self.femme.username, self.femme.email,
             self.femme.matricule, self.femme.role, self.femme.departement_id),
            ("Marie", "Nkou", "m.nkou", "marie@delifood.local", "MAT-77", "MANAGER", self.compta.pk),
        )
        # le nouveau mot de passe fonctionne, l'ancien non
        self.client.force_authenticate(user=None)
        ok = self.client.post("/api/auth/token/", {"username": "m.nkou", "password": "Nouveau#Mdp2026"}, format="json")
        self.assertEqual(ok.status_code, 200)
        ko = self.client.post("/api/auth/token/", {"username": "m.nkou", "password": MDP}, format="json")
        self.assertEqual(ko.status_code, 401)

    def test_mot_de_passe_faible_refuse_a_la_modification(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/utilisateurs/{self.femme.pk}/", {"password": "123"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_identifiant_et_matricule_doivent_rester_uniques(self):
        self.client.force_authenticate(user=self.admin)
        r1 = self.client.patch(f"/api/utilisateurs/{self.femme.pk}/", {"username": "homme"}, format="json")
        r2 = self.client.patch(f"/api/utilisateurs/{self.femme.pk}/", {"matricule": "HOMME"}, format="json")
        self.assertEqual((r1.status_code, r2.status_code), (400, 400))

    def test_seul_l_admin_peut_modifier_un_compte(self):
        for u in (self.rh, self.m_prod, self.dir_a, self.femme):
            self.client.force_authenticate(user=u)
            resp = self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"first_name": "X"}, format="json")
            self.assertEqual(resp.status_code, 403, u.username)
            resp = self.client.post(
                f"/api/utilisateurs/{self.homme.pk}/definir-mot-de-passe/",
                {"nouveau_mot_de_passe": "Autre#Mdp2026"}, format="json",
            )
            self.assertEqual(resp.status_code, 403, u.username)

    def test_modification_journalisee_sans_fuite_du_mot_de_passe(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(
            f"/api/utilisateurs/{self.homme.pk}/", {"last_name": "Changé", "password": "Nouveau#Mdp2026"},
            format="json",
        )
        entree = JournalAudit.objects.get(action="Modification utilisateur")
        self.assertEqual(entree.auteur, self.admin)
        self.assertIn("Changé", entree.valeur_apres)
        self.assertNotIn("Nouveau#Mdp2026", entree.valeur_apres + entree.valeur_avant)
        self.assertNotIn("pbkdf2", entree.valeur_apres)

    def test_dernier_admin_actif_protege(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/utilisateurs/{self.admin.pk}/", {"role": "RH"}, format="json")
        self.assertEqual(resp.status_code, 400)
        resp = self.client.patch(f"/api/utilisateurs/{self.admin.pk}/", {"actif": False}, format="json")
        self.assertEqual(resp.status_code, 400)
        # avec un second admin actif, c'est permis
        creer("admin2", RoleUtilisateur.ADMINISTRATEUR, sexe="F")
        resp = self.client.patch(f"/api/utilisateurs/{self.admin.pk}/", {"role": "RH"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_desactivation_empeche_la_connexion(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"actif": False}, format="json")
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/auth/token/", {"username": "homme", "password": MDP}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_perdre_le_role_manager_libere_le_departement(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(f"/api/utilisateurs/{self.m_prod.pk}/", {"role": "EMPLOYE", "date_embauche": "2020-01-15", "a_enfant": False}, format="json")
        self.prod.refresh_from_db()
        self.assertIsNone(self.prod.responsable)

    def test_perdre_le_role_directeur_libere_ses_departements(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch(f"/api/utilisateurs/{self.dir_a.pk}/", {"role": "RH"}, format="json")
        self.prod.refresh_from_db()
        self.compta.refresh_from_db()
        self.assertIsNone(self.prod.directeur)
        self.assertIsNone(self.compta.directeur)
        self.dir_a.refresh_from_db()
        self.assertIsNone(self.dir_a.fonction_direction)

    def test_directeur_exige_une_fonction(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(f"/api/utilisateurs/{self.homme.pk}/", {"role": "DIRECTEUR"}, format="json")
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
class JustificatifsTests(BaseV2):
    def setUp(self):
        super().setUp()
        resp = self.demande(self.femme, self.mat, self.pdf())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.demande_id = resp.data["id"]
        self.url = f"/api/demandes/{self.demande_id}/justificatif/"

    def get(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(self.url)

    def test_serializer_expose_un_lien_api_et_non_une_url_media(self):
        self.client.force_authenticate(user=self.femme)
        data = self.client.get(f"/api/demandes/{self.demande_id}/").data
        self.assertTrue(data["a_justificatif"])
        self.assertEqual(data["justificatif_url"], self.url)
        self.assertTrue(data["justificatif_nom"].endswith(".pdf"))
        self.assertNotIn("/media/", str(data))
        self.assertNotIn("justificatif_fichier", data)

    def test_visible_au_niveau_manager(self):
        resp = self.get(self.m_prod)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(b"".join(resp.streaming_content), PDF)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp["Content-Disposition"].startswith("inline"))
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")

    def test_visible_au_niveau_direction_competente(self):
        self.assertEqual(self.get(self.dir_a).status_code, 200)

    def test_visible_a_l_employe_la_rh_et_l_admin(self):
        for u in (self.femme, self.rh, self.admin):
            self.assertEqual(self.get(u).status_code, 200, u.username)

    def test_invisible_aux_autres(self):
        for u in (self.homme, self.m_compta, self.dir_b, self.emp_compta):
            self.assertEqual(self.get(u).status_code, 404, u.username)

    def test_authentification_requise(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_pas_de_route_media_publique(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/media/justificatifs/x.pdf").status_code, 404)

    def test_demande_sans_justificatif_donne_404(self):
        self.client.force_authenticate(user=self.homme)
        r = self.client.post("/api/demandes/", {
            "type_conge": self.cp.pk, "date_debut": jour(20).isoformat(), "date_fin": jour(21).isoformat(),
        }, format="json")
        self.client.force_authenticate(user=self.m_prod)
        self.assertEqual(self.client.get(f"/api/demandes/{r.data['id']}/justificatif/").status_code, 404)
        self.assertFalse(r.data["a_justificatif"])

    def test_formats_dangereux_refuses(self):
        html = SimpleUploadedFile("page.html", b"<script>alert(1)</script>", content_type="text/html")
        svg = SimpleUploadedFile("x.svg", b"<svg onload=alert(1)/>", content_type="image/svg+xml")
        faux = SimpleUploadedFile("faux.pdf", b"<script>alert(1)</script>", content_type="application/pdf")
        for f in (html, svg, faux):
            resp = self.demande(self.homme, self.maladie, f, debut=40, fin=41)
            self.assertEqual(resp.status_code, 400, f.name)

    def test_taille_maximale(self):
        gros = SimpleUploadedFile("gros.pdf", PDF + b"0" * (5 * 1024 * 1024), content_type="application/pdf")
        self.assertEqual(self.demande(self.homme, self.maladie, gros, debut=40, fin=41).status_code, 400)

    def test_png_accepte(self):
        png = SimpleUploadedFile("scan.png", PNG, content_type="image/png")
        self.assertEqual(self.demande(self.homme, self.maladie, png, debut=40, fin=41).status_code, 201)

    def test_les_demandes_ne_sont_ni_modifiables_ni_supprimables(self):
        self.client.force_authenticate(user=self.femme)
        url = f"/api/demandes/{self.demande_id}/"
        self.assertEqual(self.client.patch(url, {"motif": "x"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)


# ---------------------------------------------------------------------------
class DirecteurMultiDepartementsTests(BaseV2):
    def soumettre(self, user):
        resp = self.demande(user, self.cp, debut=15, fin=16)
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data["id"]

    def approuver_manager(self, manager, demande_id):
        self.client.force_authenticate(user=manager)
        resp = self.client.post(
            f"/api/demandes/{demande_id}/valider-manager/", {"decision": "APPROUVE"}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def ids_vus(self, user):
        self.client.force_authenticate(user=user)
        return {d["id"] for d in self.client.get("/api/demandes/").data["results"]}

    def test_un_directeur_a_plusieurs_departements(self):
        self.assertEqual(
            set(self.dir_a.departements_supervises.values_list("nom", flat=True)),
            {"Production", "Comptabilité"},
        )
        self.client.force_authenticate(user=self.admin)
        profil = self.client.get(f"/api/utilisateurs/{self.dir_a.pk}/").data
        self.assertEqual({d["nom"] for d in profil["departements_supervises"]}, {"Production", "Comptabilité"})

    def test_perimetre_de_vision_du_directeur(self):
        d_prod = self.soumettre(self.femme)
        d_compta = self.soumettre(self.emp_compta)
        d_logi = self.soumettre(self.emp_logi)
        # dir_a : Production + Comptabilité + département sans directeur (Logistique)
        self.assertEqual(self.ids_vus(self.dir_a), {d_prod, d_compta, d_logi})
        # dir_b ne supervise rien : ne voit que le département sans directeur
        self.assertEqual(self.ids_vus(self.dir_b), {d_logi})

    def test_directeur_hors_perimetre_ne_peut_pas_decider(self):
        d_prod = self.soumettre(self.femme)
        self.approuver_manager(self.m_prod, d_prod)
        self.client.force_authenticate(user=self.dir_b)
        resp = self.client.post(f"/api/demandes/{d_prod}/valider-direction/", {"decision": "APPROUVE"}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.client.force_authenticate(user=self.dir_a)
        resp = self.client.post(f"/api/demandes/{d_prod}/valider-direction/", {"decision": "APPROUVE"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], "VALIDEE")

    def test_notification_envoyee_au_bon_directeur(self):
        d_prod = self.soumettre(self.femme)
        self.approuver_manager(self.m_prod, d_prod)
        self.assertTrue(Notification.objects.filter(utilisateur=self.dir_a, demande_id=d_prod).exists())
        self.assertFalse(Notification.objects.filter(utilisateur=self.dir_b, demande_id=d_prod).exists())

    def test_departement_sans_directeur_repli_sur_toute_la_direction(self):
        d_logi = self.soumettre(self.emp_logi)
        # Pas de responsable Logistique : on force l'état d'attente Direction
        from conges.models import DemandeConge, StatutDemande
        DemandeConge.objects.filter(pk=d_logi).update(statut=StatutDemande.EN_ATTENTE_DIRECTION)
        for d in (self.dir_a, self.dir_b):
            self.client.force_authenticate(user=d)
            self.assertEqual(self.client.get(f"/api/demandes/{d_logi}/").status_code, 200)

    def test_admin_affecte_plusieurs_departements_via_le_compte(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            f"/api/utilisateurs/{self.dir_b.pk}/",
            {"departements_supervises": [self.logistique.pk, self.compta.pk]}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual({d["nom"] for d in resp.data["departements_supervises"]}, {"Logistique", "Comptabilité"})
        # Comptabilité a été retirée à dir_a (un département = un directeur)
        self.assertEqual(
            set(self.dir_a.departements_supervises.values_list("nom", flat=True)), {"Production"}
        )

    def test_creation_d_un_directeur_avec_ses_departements(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/utilisateurs/", {
            "username": "dg", "password": "Zx9#kLm!2026", "first_name": "D", "last_name": "G",
            "matricule": "DG1", "role": "DIRECTEUR", "fonction_direction": "DG", "sexe": "M",
            "departements_supervises": [self.logistique.pk],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.logistique.refresh_from_db()
        self.assertEqual(self.logistique.directeur.username, "dg")

    def test_seul_un_directeur_peut_superviser(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            f"/api/utilisateurs/{self.homme.pk}/", {"departements_supervises": [self.prod.pk]}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.patch(
            f"/api/departements/{self.logistique.pk}/", {"directeur": self.homme.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_affectation_du_directeur_depuis_le_departement(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            f"/api/departements/{self.logistique.pk}/", {"directeur": self.dir_b.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["directeur_nom"], self.dir_b.get_full_name())
        self.assertEqual(self.dir_b.departements_supervises.count(), 1)

    def test_responsable_doit_etre_manager(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            f"/api/departements/{self.logistique.pk}/", {"responsable": self.homme.pk}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
