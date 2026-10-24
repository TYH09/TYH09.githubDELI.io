"""
Parcours de bout en bout dans un vrai navigateur (Playwright/Chromium) :
tous les rôles, le circuit de validation à deux niveaux, le RBAC des routes,
la déconnexion/reconnexion et le retour vers un lien profond.

Prérequis : backend Django sur 127.0.0.1:8000 (base fraîchement migrée +
`python manage.py seed_demo`) et frontend Vite sur 127.0.0.1:5173.
Lancement : python3 e2e/parcours_complet.py   (code de sortie 1 en cas d'échec)
"""
import datetime
import re
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
MDP = "Conges#2026"
MDP_NADINE = "Reinit#2026ab"   # mot de passe défini par l'admin lors de la modification du compte
MDP_DIR = "Direction#2026ab"
resultats = []
erreurs_js = []          # exceptions JavaScript non interceptées (toujours inattendues)
reponses_en_erreur = []  # « STATUT MÉTHODE /chemin » de chaque réponse HTTP >= 400

# Réponses d'erreur que le parcours provoque VOLONTAIREMENT (chacune une seule fois) :
#  - 401 sur la connexion : test « mauvais mot de passe »
#  - 400 sur la création de demande : test de la règle du délai minimum
#    (la règle « maternité une seule fois par an » est couverte par les tests unitaires : en fin
#    d'année, deux congés de 90 jours ne peuvent pas tenir sans se chevaucher)
#  - 400 sur la suppression d'un département encore peuplé : test du garde-fou
ATTENDUES = {"401 POST /api/auth/token/": 1, "400 POST /api/demandes/": 1, "400 DELETE /api/departements/N/": 1}

# PNG 1x1 valide : justificatif léger qui s'affiche en ligne dans l'onglet (même en Chromium headless)
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050001a5f645400000000049454e44ae426082"
)


def check(label, condition):
    resultats.append(bool(condition))
    print(("  OK    " if condition else "  ÉCHEC ") + label, flush=True)


def login(page, user, pwd=MDP):
    page.goto(BASE + "/connexion")
    page.fill("input[type=text]", user)
    page.fill("input[type=password]", pwd)
    page.click("button[type=submit]")
    page.wait_for_selector("text=Bonjour", timeout=15000)


def logout(page):
    page.click("text=Déconnexion")
    page.wait_for_url("**/connexion", timeout=8000)


def nav(page):
    return [a.inner_text().strip() for a in page.query_selector_all("nav.entete__nav a")]


def nouveau_contexte(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="fr-FR", accept_downloads=True)
    page = ctx.new_page()
    page.on("pageerror", lambda e: erreurs_js.append(str(e)[:150]))
    page.on(
        "response",
        lambda r: reponses_en_erreur.append(
            f"{r.status} {r.request.method} {re.sub(r'/[0-9]+/', '/N/', r.url.replace(BASE, '').split('?')[0])}"
        )
        if r.status >= 400 else None,
    )
    return page


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = nouveau_contexte(browser)
    jour = datetime.date.today()

    FERIES_RECURRENTS = {(1, 1), (2, 11), (4, 3), (5, 1), (5, 20), (8, 15), (12, 25)}  # jeu de démonstration

    def retour_apres(d):
        """Premier jour de travail après le dernier jour d'absence d (week-ends et fériés exclus)."""
        d += datetime.timedelta(days=1)
        while d.weekday() >= 5 or (d.month, d.day) in FERIES_RECURRENTS:
            d += datetime.timedelta(days=1)
        return d

    def fr(d):
        return d.strftime("%d/%m/%Y")

    def ouvre(n):
        """Premier jour ouvré (lun-ven) à partir d'aujourd'hui + n jours : évite les week-ends."""
        d = jour + datetime.timedelta(days=n)
        while d.weekday() >= 5:
            d += datetime.timedelta(days=1)
        return d

    print("== Connexion ==")
    page.goto(BASE + "/")
    page.wait_for_url("**/connexion")
    check("accès non connecté -> redirigé vers /connexion", page.url.endswith("/connexion"))
    page.fill("input[type=text]", "e.employe"); page.fill("input[type=password]", "mauvais")
    page.click("button[type=submit]"); page.wait_for_selector("text=Identifiants incorrects", timeout=8000)
    check("mauvais mot de passe -> message d'erreur", True)

    print("== EMPLOYÉ ==")
    login(page, "e.employe")
    labels = nav(page)
    check("menu employé : Mes demandes présent", any("Mes demandes" in l for l in labels))
    check("menu employé : aucun lien RH/Admin/validation",
          not any(k in " ".join(labels) for k in ("Utilisateurs", "Indicateurs RH", "à valider", "Paramètres")))
    check("solde de 18 jours affiché", page.is_visible("text=18"))
    page.goto(BASE + "/mes-demandes")
    page.click("text=+ Nouvelle demande")
    options = [o.inner_text() for o in page.query_selector_all("form select option")]
    check("employé (M) : « Congé de paternité » proposé", any("paternité" in o for o in options))
    check("employé (M) : « Congé de maternité » NON proposé", not any("maternité" in o for o in options))
    page.select_option("form select", label="Congé annuel")
    page.fill("input[type=date] >> nth=0", ouvre(25).isoformat())
    page.fill("input[type=date] >> nth=1", ouvre(27).isoformat())
    page.fill("form input[type=text]", "Vacances test E2E")
    page.click("text=Soumettre la demande")
    page.wait_for_selector("text=En attente — Manager", timeout=10000)
    check("demande soumise -> statut « En attente — Manager »", True)
    for route in ("/rh/dashboard", "/admin/utilisateurs", "/validations/manager", "/validations/direction", "/admin/parametres", "/absences"):
        page.goto(BASE + route); page.wait_for_timeout(500)
        check(f"employé sur {route} -> /acces-refuse", page.url.endswith("/acces-refuse"))

    print("== BUG CORRIGÉ : déconnexion depuis une page d'employé puis reconnexion immédiate d'un autre rôle ==")
    page.goto(BASE + "/mes-demandes"); page.wait_for_selector("text=Historique")
    logout(page)
    check("après déconnexion, aucune destination mémorisée (état de navigation vide)",
          page.evaluate("window.history.state && window.history.state.usr ? JSON.stringify(window.history.state.usr) : ''") in ("", "null", "{}"))
    login(page, "j.manager")
    check("le manager reconnecté atterrit sur le tableau de bord (pas sur /acces-refuse)", page.url.rstrip("/") == BASE)

    print("== MANAGER ==")
    labels = nav(page)
    check("menu manager : Demandes à valider + Mon équipe", any("à valider" in l for l in labels) and any("équipe" in l for l in labels))
    check("menu manager : pas de « Mes demandes »", not any("Mes demandes" in l for l in labels))
    page.goto(BASE + "/validations/manager"); page.wait_for_selector("text=Eric Talla", timeout=10000)
    check("le manager voit la demande d'Eric Talla", True)
    page.goto(BASE + "/notifications")
    page.click("text=Nouvelle demande de congé de Eric Talla")
    page.wait_for_url(re.compile(r".*/demandes/\d+$"), timeout=8000)
    check("le MANAGER clique sur une notification -> redirigé vers la demande (/demandes/<id>)",
          re.search(r"/demandes/\d+$", page.url) is not None)
    page.wait_for_selector("text=Votre décision", timeout=8000)
    check("la page de la demande affiche le formulaire de décision du manager",
          page.is_visible("text=Eric Talla") and page.is_visible("text=Votre décision"))
    page.get_by_label("Commentaire (optionnel)").fill("Validé côté équipe")
    page.click("button:has-text('Approuver')"); page.wait_for_selector("text=Demande approuvée", timeout=10000)
    check("le manager approuve la demande depuis sa page de détail", True)
    page.goto(BASE + "/validations/manager"); page.wait_for_selector("text=Aucune demande en attente", timeout=10000)
    check("après approbation, la file du manager est vide", True)
    page.goto(BASE + "/equipe"); page.wait_for_selector("text=Eric", timeout=8000)
    check("« Mon équipe » liste les membres du département", True)
    page.goto(BASE + "/inexistante"); page.wait_for_selector("text=404", timeout=8000)
    check("route inconnue -> page 404", True)
    page.goto(BASE + "/validations/direction"); page.wait_for_timeout(500)
    check("manager sur /validations/direction -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/"); logout(page)

    print("== DIRECTION GÉNÉRALE ==")
    login(page, "p.directeur")
    check("menu direction : Demandes à valider", any("à valider" in l for l in nav(page)))
    page.goto(BASE + "/validations/direction"); page.wait_for_selector("text=Eric Talla", timeout=10000)
    check("la direction voit la demande approuvée par le manager", True)
    page.goto(BASE + "/notifications")
    page.click("text=requiert votre validation >> nth=0")
    page.wait_for_url(re.compile(r".*/demandes/\d+$"), timeout=8000)
    check("le DIRECTEUR clique sur une notification -> redirigé vers la demande (/demandes/<id>)",
          re.search(r"/demandes/\d+$", page.url) is not None)
    page.wait_for_selector("text=Votre décision", timeout=8000)
    check("la page de la demande affiche le formulaire de décision de la direction",
          page.is_visible("text=Eric Talla") and page.is_visible("text=Chef de département"))
    page.click("button:has-text('Approuver')"); page.wait_for_selector("text=Demande approuvée", timeout=10000)
    page.goto(BASE + "/validations/direction"); page.wait_for_selector("text=Aucune demande en attente", timeout=10000)
    check("validation finale effectuée par la direction", True)
    page.goto(BASE + "/validations/manager"); page.wait_for_timeout(500)
    check("direction sur /validations/manager -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/"); logout(page)

    print("== EMPLOYÉ (retour) ==")
    login(page, "e.employe")
    page.goto(BASE + "/mes-demandes"); page.wait_for_selector("text=Validée", timeout=10000)
    check("l'employé voit sa demande « Validée »", True)
    page.click("text=Détails"); page.wait_for_selector("text=Direction Générale", timeout=8000)
    check("historique des 2 validations (Chef de département + Direction)", page.is_visible("text=Chef de département"))
    page.goto(BASE + "/notifications"); page.wait_for_selector("text=validée", timeout=8000)
    check("notification « demande validée » reçue", True)
    page.click("text=validée >> nth=0")
    page.wait_for_url(re.compile(r".*/demandes/\d+$"), timeout=8000)
    page.wait_for_selector("text=Validée", timeout=8000)
    check("l'EMPLOYÉ clique sur sa notification -> détail de sa demande (statut Validée)", True)
    page.goto(BASE + "/"); page.wait_for_selector("text=j. restants", timeout=8000)
    check("solde décrémenté (≠ 18 j.)", not page.is_visible("text=18 j. restants"))
    logout(page)

    print("== JUSTIFICATIF visible aux deux niveaux de validation ==")
    login(page, "e.employe")
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé de paternité")
    page.fill("input[type=date] >> nth=0", ouvre(60).isoformat())
    page.fill("input[type=date] >> nth=1", ouvre(61).isoformat())
    page.set_input_files("input[type=file]", files=[{"name": "acte_naissance.png", "mimeType": "image/png", "buffer": PNG_1X1}])
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=En attente — Manager", timeout=10000)
    check("l'employé (M) soumet un congé de paternité avec justificatif", True)
    page.click("tr:has-text('paternité') >> text=Détails")
    page.wait_for_selector("text=Voir le justificatif", timeout=8000)
    with page.context.expect_page(timeout=8000) as nouvel_onglet:
        page.click("text=Voir le justificatif")
    onglet = nouvel_onglet.value
    onglet.wait_for_function("location.href.startsWith('blob:')", timeout=8000)
    check("l'employé ouvre son justificatif (onglet blob)", onglet.url.startswith("blob:"))
    onglet.close(); logout(page)

    login(page, "j.manager")
    page.goto(BASE + "/validations/manager"); page.wait_for_selector("text=Eric Talla", timeout=10000)
    with page.context.expect_page(timeout=8000) as nouvel_onglet:
        page.click("text=Voir le justificatif")
    onglet = nouvel_onglet.value
    onglet.wait_for_function("location.href.startsWith('blob:')", timeout=8000)
    check("le MANAGER (1er niveau) ouvre le justificatif", onglet.url.startswith("blob:"))
    onglet.close()
    page.click("text=Approuver"); page.wait_for_selector("text=Aucune demande en attente", timeout=10000)
    logout(page)

    login(page, "p.directeur")
    page.goto(BASE + "/validations/direction"); page.wait_for_selector("text=Eric Talla", timeout=10000)
    with page.context.expect_page(timeout=8000) as nouvel_onglet:
        page.click("text=Voir le justificatif")
    onglet = nouvel_onglet.value
    onglet.wait_for_function("location.href.startsWith('blob:')", timeout=8000)
    check("la DIRECTION (2e niveau) ouvre le justificatif", onglet.url.startswith("blob:"))
    onglet.close()
    page.click("text=Approuver"); page.wait_for_selector("text=Aucune demande en attente", timeout=10000)
    check("la direction valide le congé de paternité", True)
    logout(page)

    print("== EMPLOYÉ : demande laissée en attente (pour vérifier que l'export l'exclut) ==")
    login(page, "e.employe")
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé annuel")
    page.fill("input[type=date] >> nth=0", ouvre(90).isoformat())
    page.fill("input[type=date] >> nth=1", ouvre(91).isoformat())
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=En attente — Manager", timeout=10000)
    check("l'employé laisse une demande « Congé annuel » en attente (hors export)", True)
    logout(page)

    print("== MANAGER : absences de l'équipe ==")
    login(page, "j.manager")
    check("menu manager : lien « Absences »", any("Absences" in l for l in nav(page)))
    page.wait_for_selector("text=Absents aujourd’hui", timeout=8000)
    check("tableau de bord manager : carte « Absents aujourd’hui »", True)
    page.goto(BASE + "/absences"); page.wait_for_selector("text=Eric Talla", timeout=10000)
    lignes = page.query_selector_all("tbody tr")
    check("la liste contient les 2 congés validés d'Eric Talla (congé annuel + paternité)", len(lignes) == 2)
    ligne = page.locator("tbody tr").first
    texte = ligne.inner_text()
    check("ligne : nom, rôle, e-mail et téléphone",
          all(k in texte for k in ("Eric Talla", "Employé", "e.employe@delifood-agro.local", "+237 6 91 23 45 67")))
    check("ligne : date de départ et date de retour (1er congé)",
          fr(ouvre(25)) in texte and fr(retour_apres(ouvre(27))) in texte)
    check("le téléphone est un lien cliquable tel:", page.is_visible("a[href^='tel:+237691234567']"))
    check("le motif et le type de congé ne sont pas affichés",
          not any(k in page.inner_text("main") for k in ("Vacances test E2E", "Congé annuel", "paternité")))
    page.select_option("select", "en_cours")
    page.wait_for_selector("text=Aucun collaborateur en congé sur cette période", timeout=8000)
    check("filtre « En congé aujourd'hui » : personne (les congés sont à venir)", True)
    page.select_option("select", "a_venir"); page.wait_for_selector("tbody tr", timeout=8000)
    check("filtre « Départs à venir » : 2 lignes", len(page.query_selector_all("tbody tr")) == 2)
    page.goto(BASE + "/"); logout(page)
    login(page, "p.directeur")
    page.goto(BASE + "/absences"); page.wait_for_timeout(500)
    check("direction sur /absences -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/"); logout(page)

    print("== RH ==")
    login(page, "r.rh")
    labels = nav(page)
    check("menu RH : Types / Jours fériés / Export", all(any(k in l for l in labels) for k in ("Types", "fériés", "Export")))
    check("menu RH : ni Utilisateurs ni Paramètres", not any(k in " ".join(labels) for k in ("Utilisateurs", "Paramètres")))
    page.goto(BASE + "/rh/jours-feries"); page.wait_for_selector("text=Jours déclarés", timeout=8000)
    page.fill("input[type=date]", "2026-11-20"); page.get_by_label("Libellé").fill("Fermeture test E2E")
    page.click("button:has-text('Ajouter')"); page.wait_for_selector("td:has-text('Fermeture test E2E')", timeout=8000)
    check("la RH ajoute une fermeture", True)
    page.goto(BASE + "/rh/types-conge"); page.wait_for_selector("text=Types existants", timeout=8000)
    page.get_by_label("Libellé").fill("Congé formation E2E")
    page.get_by_label("Réservé à un sexe").select_option("F")
    page.click("button:has-text('Ajouter')"); page.wait_for_selector("td:has-text('Congé formation E2E')", timeout=8000)
    check("la RH réserve un type de congé aux femmes", page.is_visible("tr:has-text('Congé formation E2E') >> text=Femmes"))
    check("la RH crée un type de congé (règle d'acquisition vide -> défaut « annuelle »)", page.is_visible("td:has-text('annuelle')"))
    page.goto(BASE + "/rh/export"); page.wait_for_selector("text=Export des congés validés", timeout=8000)
    check("plus de bouton de téléchargement Excel sur la page d'export",
          page.locator("text=Excel").count() == 0 and page.locator("text=.xlsx").count() == 0)
    with page.expect_download(timeout=15000) as dl:
        page.click("text=Télécharger le CSV")
    contenu = open(dl.value.path(), encoding="utf-8-sig").read()
    check("export CSV téléchargé via l'interface (JWT inclus)", "Employé" in contenu and "Talla" in contenu)
    check("le fichier téléchargé est un .csv", dl.value.suggested_filename.endswith(".csv"))
    check("CSV : uniquement les demandes validées (2 lignes + en-tête)", len(contenu.strip().splitlines()) == 3)
    check("CSV : la demande en attente (Congé annuel du " + ouvre(90).isoformat() + ") est exclue",
          ouvre(90).isoformat() not in contenu and "paternité" in contenu)
    page.goto(BASE + "/rh/dashboard"); page.wait_for_selector("text=Effectifs et congés par département", timeout=8000)
    check("indicateurs RH affichés", True)
    check("RH : colonnes effectif total / éligibles au congé annuel / ont pris un congé",
          all(page.is_visible(f"th:has-text('{k}')") for k in ("Effectif total", "Éligibles au congé annuel", "Ont pris un congé")))
    entetes = [t.inner_text().strip() for t in page.query_selector_all("table.tableau--chiffres thead th")]
    ligne_prod = [t.inner_text().strip() for t in page.query_selector_all("table.tableau--chiffres tbody tr:has-text('Production') td")]
    check("RH : ligne Production = effectif 3 (manager + 2 employés), 2 employés, 1 éligible",
          len(ligne_prod) == len(entetes) and ligne_prod[1] == "3" and ligne_prod[2] == "2" and ligne_prod[3] == "1")
    check("RH : ligne « Total » présente", page.is_visible("table.tableau--chiffres tfoot >> text=Total"))
    page.goto(BASE + "/admin/utilisateurs"); page.wait_for_timeout(500)
    check("RH sur /admin/utilisateurs -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/admin/types-conge"); page.wait_for_timeout(500)
    check("RH sur /admin/types-conge (seuils par type, réservé Admin) -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/absences"); page.wait_for_timeout(500)
    check("RH sur /absences -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/"); logout(page)

    print("== ADMINISTRATEUR ==")
    login(page, "a.admin")
    labels = nav(page)
    check("menu admin : Utilisateurs / Départements / Paramètres", all(any(k in l for l in labels) for k in ("Utilisateurs", "Départements", "Paramètres")))
    page.goto(BASE + "/admin/utilisateurs"); page.wait_for_selector("text=Annuaire", timeout=10000)
    page.click("text=+ Nouveau compte")
    page.get_by_label("Identifiant", exact=True).fill("n.nouveau")
    page.get_by_label("Mot de passe", exact=True).fill("Nouveau#2026")
    page.get_by_label("Prénom", exact=True).fill("Nadia")
    page.get_by_label("Nom", exact=True).fill("Nouveau")
    page.get_by_label("Matricule", exact=True).fill("N900")
    page.get_by_label("Téléphone (facultatif)").fill("+237 6 70 12 34 56")
    page.click("text=Créer le compte")
    page.wait_for_timeout(600)
    check("sexe obligatoire : création refusée côté navigateur tant que non choisi",
          not page.is_visible("td:has-text('n.nouveau')"))
    page.get_by_label("Sexe").select_option("F")
    page.click("text=Créer le compte")
    page.wait_for_timeout(600)
    check("date d'entrée obligatoire pour un employé : création refusée tant qu'elle manque",
          not page.is_visible("td:has-text('n.nouveau')"))
    champ_date = page.locator("label:has-text('Date d’entrée') input")
    champ_date.fill((jour.replace(year=jour.year - 3) - datetime.timedelta(days=10)).isoformat())
    check("indication en direct : 3 ans d'ancienneté -> droit à 18 jours de congé annuel par an",
          page.is_visible("text=droit à 18 jours de congé annuel par an"))
    champ_date.fill((jour - datetime.timedelta(days=60)).isoformat())
    check("indication en direct : moins d'un an -> pas de solde de congé annuel",
          page.is_visible("text=Moins d’un an d’ancienneté"))
    champ_date.fill((jour.replace(year=jour.year - 3) - datetime.timedelta(days=10)).isoformat())
    check("employée : question « A-t-elle un enfant ? » affichée (Oui / Non)",
          page.is_visible("text=A-t-elle un enfant ?") and page.locator("input[name=a_enfant]").count() == 2)
    page.click("text=Créer le compte"); page.wait_for_timeout(600)
    check("employée : la réponse « enfant oui/non » est obligatoire (création refusée sinon)",
          not page.is_visible("td:has-text('n.nouveau')"))
    page.locator("input[name=a_enfant][value=oui]").check()
    champ_age = page.get_by_label(re.compile("Âge du dernier enfant"))
    check("« Oui » : le champ « âge du dernier enfant » apparaît", champ_age.is_visible())
    champ_age.fill("8")
    check("dernier enfant de 8 ans (> 6) -> 18 jours de congé annuel", page.is_visible("text=droit à 18 jours de congé annuel par an"))
    champ_age.fill("6")
    check("dernier enfant de 6 ans (limite) -> 21 jours", page.is_visible("text=droit à 21 jours de congé annuel par an"))
    champ_age.fill("4")
    check("dernier enfant de 4 ans (≤ 6) -> 21 jours", page.is_visible("text=droit à 21 jours de congé annuel par an"))
    page.locator("input[name=a_enfant][value=non]").check()
    check("« Non » : le champ âge disparaît et le droit repasse à 18 jours",
          not champ_age.is_visible() and page.is_visible("text=droit à 18 jours de congé annuel par an"))
    page.locator("input[name=a_enfant][value=oui]").check()
    page.get_by_label(re.compile("Âge du dernier enfant")).fill("4")
    page.click("text=Créer le compte"); page.wait_for_selector("td:has-text('n.nouveau')", timeout=10000)
    check("annuaire : ancienneté « 3 ans » + badge « Congé annuel · 21 j » pour le compte créé",
          page.is_visible("tr:has-text('n.nouveau') >> text=3 ans") and page.is_visible("tr:has-text('n.nouveau') >> text=Congé annuel · 21 j"))
    check("l'admin crée un compte avec le sexe Féminin", page.is_visible("tr:has-text('n.nouveau') >> text=F"))
    check("le numéro de téléphone saisi à la création apparaît dans l'annuaire",
          page.is_visible("tr:has-text('n.nouveau') >> text=+237 6 70 12 34 56"))

    print("== ADMINISTRATEUR : modification complète d'un compte ==")
    page.click("tr:has-text('n.nouveau') >> text=Modifier")
    page.wait_for_selector("text=Modifier le compte de Nadia Nouveau", timeout=8000)
    page.get_by_label("Identifiant", exact=True).fill("n.nadine")
    page.get_by_label("Prénom", exact=True).fill("Nadine")
    page.get_by_label("Nom", exact=True).fill("Nkou")
    page.get_by_label("E-mail").fill("nadine.nkou@delifood-agro.local")
    page.get_by_label("Téléphone (facultatif)").fill("690 11 22 33")
    page.locator("label", has_text=re.compile(r"^Département")).locator("select").select_option(label="Production")
    page.get_by_label("Nouveau mot de passe (laisser vide pour ne pas le changer)").fill(MDP_NADINE)
    page.click("text=Enregistrer les modifications")
    page.wait_for_selector("tr:has-text('n.nadine'):has-text('Nadine Nkou'):has-text('Production')", timeout=10000)
    check("l'admin modifie identifiant, prénom, nom, e-mail, département et mot de passe", True)
    check("l'ancien identifiant a disparu de l'annuaire", not page.is_visible("td:has-text('n.nouveau')"))
    check("le téléphone a été modifié", page.is_visible("tr:has-text('n.nadine') >> text=690 11 22 33"))

    print("== ADMINISTRATEUR : tri de l'annuaire par département et par rôle ==")
    def colonne(i):
        return [r.query_selector_all("td")[i].inner_text().strip() for r in page.query_selector_all("tbody tr")]
    page.click("th button:has-text('Département')"); page.wait_for_timeout(300)
    deps = colonne(5)
    nommes = [d for d in deps if d not in ("", "—")]
    check("tri par département (croissant) : ordre alphabétique, sans-département en dernier",
          nommes == sorted(nommes, key=str.casefold) and deps[len(nommes):] == [d for d in deps if d in ("", "—")])
    page.click("th button:has-text('Département')"); page.wait_for_timeout(300)
    deps = colonne(5)
    nommes = [d for d in deps if d not in ("", "—")]
    check("2e clic : tri par département décroissant", nommes == sorted(nommes, key=str.casefold, reverse=True))
    page.click("th button:has-text('Rôle')"); page.wait_for_timeout(300)
    roles = colonne(4)
    ordre = ["Employé", "Manager", "Direction", "Responsable RH", "Administrateur"]
    rangs = [next(i for i, o in enumerate(ordre) if r.startswith(o)) for r in roles]
    check("tri par rôle : Employé, Manager, Direction, RH, Administrateur", rangs == sorted(rangs) and len(set(rangs)) == 5)
    page.click("th button:has-text('Rôle')"); page.wait_for_timeout(300)
    rangs = [next(i for i, o in enumerate(ordre) if r.startswith(o)) for r in colonne(4)]
    check("2e clic : tri par rôle inversé", rangs == sorted(rangs, reverse=True))

    print("== ADMINISTRATEUR : suppression d'un employé ==")
    page.click("text=+ Nouveau compte")
    page.get_by_label("Identifiant", exact=True).fill("t.jetable")
    page.get_by_label("Mot de passe", exact=True).fill("Jetable#2026xy")
    page.get_by_label("Prénom", exact=True).fill("Théo")
    page.get_by_label("Nom", exact=True).fill("Jetable")
    page.get_by_label("Matricule", exact=True).fill("J900")
    page.get_by_label("Sexe").select_option("M")
    page.locator("label:has-text('Date d’entrée') input").fill((jour - datetime.timedelta(days=60)).isoformat())
    page.click("text=Créer le compte"); page.wait_for_selector("td:has-text('t.jetable')", timeout=10000)
    check("compte jetable créé (sans téléphone : champ facultatif)",
          page.is_visible("tr:has-text('t.jetable') >> text=téléphone non renseigné"))
    check("annuaire : badge « Pas de solde » pour un employé de moins d'un an",
          page.is_visible("tr:has-text('t.jetable') >> text=Pas de solde"))
    check("pas de bouton « Supprimer » sur son propre compte",
          page.locator("tr:has-text('a.admin') >> button:has-text('Supprimer')").count() == 0)
    page.once("dialog", lambda d: d.dismiss())
    page.click("tr:has-text('t.jetable') >> text=Supprimer"); page.wait_for_timeout(500)
    check("suppression annulée dans la confirmation -> le compte reste", page.is_visible("td:has-text('t.jetable')"))
    page.once("dialog", lambda d: d.accept())
    page.click("tr:has-text('t.jetable') >> text=Supprimer")
    page.wait_for_selector("text=Compte de Théo Jetable supprimé", timeout=8000)
    check("l'admin supprime un employé", not page.is_visible("td:has-text('t.jetable')"))

    page.goto(BASE + "/admin/departements"); page.wait_for_selector("text=Départements existants", timeout=8000)
    for nom in ("Logistique", "Qualité"):
        page.fill("form input", nom); page.click("button:has-text('Créer')")
        page.wait_for_selector(f"td:has-text('{nom}')", timeout=8000)
    check("l'admin crée des départements", True)

    print("== ADMINISTRATEUR : suppression de départements ==")
    page.fill("form input", "Archives"); page.click("button:has-text('Créer')")
    page.wait_for_selector("td:has-text('Archives')", timeout=8000)
    page.once("dialog", lambda d: d.accept())
    page.click("tr:has-text('Archives') >> text=Supprimer")
    page.wait_for_selector("td:has-text('Archives')", state="detached", timeout=8000)
    check("l'admin supprime un département vide", True)
    page.once("dialog", lambda d: d.accept())
    page.click("tr:has-text('Production') >> text=Supprimer")
    page.wait_for_selector("text=Impossible de supprimer « Production »", timeout=8000)
    check("département encore peuplé : suppression refusée avec un message clair",
          page.is_visible("td:has-text('Production')"))

    print("== ADMINISTRATEUR : un directeur supervise plusieurs départements ==")
    page.goto(BASE + "/admin/utilisateurs"); page.wait_for_selector("text=Annuaire", timeout=10000)
    page.click("text=+ Nouveau compte")
    page.get_by_label("Identifiant", exact=True).fill("d.multi")
    page.get_by_label("Mot de passe", exact=True).fill(MDP_DIR)
    page.get_by_label("Prénom", exact=True).fill("Didier")
    page.get_by_label("Nom", exact=True).fill("Multi")
    page.get_by_label("Matricule", exact=True).fill("D900")
    page.get_by_label("Sexe").select_option("M")
    page.get_by_label("Rôle").select_option("DIRECTEUR")
    page.get_by_label("Fonction de direction").select_option("DAF")
    page.get_by_role("checkbox", name="Logistique").check()
    page.get_by_role("checkbox", name="Qualité").check()
    page.click("text=Créer le compte")
    page.wait_for_selector("tr:has-text('d.multi'):has-text('Logistique, Qualité')", timeout=10000)
    check("directeur créé avec 2 départements supervisés (annuaire : « Logistique, Qualité »)", True)
    page.goto(BASE + "/admin/departements"); page.wait_for_selector("text=Départements existants", timeout=8000)
    page.wait_for_selector("select[aria-label='Directeur de Logistique']", timeout=8000)
    page.wait_for_function(
        "document.querySelector(\"select[aria-label='Directeur de Logistique']\").selectedOptions[0].textContent.includes('Didier')",
        timeout=8000,
    )
    check("page Départements : Logistique -> Didier Multi",
          "Didier" in page.eval_on_selector("select[aria-label='Directeur de Logistique']", "e => e.selectedOptions[0].textContent"))
    check("page Départements : Qualité -> Didier Multi",
          "Didier" in page.eval_on_selector("select[aria-label='Directeur de Qualité']", "e => e.selectedOptions[0].textContent"))
    page.goto(BASE + "/admin/parametres"); page.wait_for_selector("text=Seuils configurables", timeout=8000)
    page.fill("label:has-text('Délai minimum') input", "5")
    page.click("text=Enregistrer"); page.wait_for_selector("text=Paramètres enregistrés", timeout=8000)
    check("l'admin passe le délai minimum à 5 jours", True)
    page.goto(BASE + "/admin/types-conge"); page.wait_for_selector("text=Types définis par la RH", timeout=8000)
    check("l'admin voit les types de congé définis par la RH",
          all(page.is_visible(f"td:has-text('{t}')") for t in ("Congé annuel", "Congé de paternité", "Congé formation E2E")))
    check("bouton Enregistrer désactivé tant qu'un type n'est pas modifié",
          page.is_disabled("button[aria-label='Enregistrer Congé annuel']"))
    page.get_by_label("Délai minimum de Congé annuel").fill("30")
    page.get_by_label("Seuil d’alerte de Congé annuel").fill("20")
    page.click("button[aria-label='Enregistrer Congé annuel']")
    page.wait_for_selector("text=Seuils de « Congé annuel » enregistrés", timeout=8000)
    check("l'admin configure délai minimum (30 j) et seuil d'alerte (20 j) pour le congé annuel", True)
    page.reload(); page.wait_for_selector("text=Types définis par la RH", timeout=8000)
    check("les seuils par type sont conservés après rechargement",
          page.get_by_label("Délai minimum de Congé annuel").input_value() == "30"
          and page.get_by_label("Seuil d’alerte de Congé annuel").input_value() == "20"
          and page.get_by_label("Délai minimum de Congé de paternité").input_value() == "")
    page.goto(BASE + "/rh/dashboard"); page.wait_for_timeout(500)
    check("admin sur /rh/dashboard (réservé RH) -> /acces-refuse", page.url.endswith("/acces-refuse"))
    page.goto(BASE + "/"); logout(page)

    print("== Directeur multi-départements : connexion ==")
    login(page, "d.multi", MDP_DIR)
    page.goto(BASE + "/mon-compte"); page.wait_for_selector("text=Départements supervisés", timeout=8000)
    check("le directeur voit ses départements supervisés (Logistique, Qualité)",
          page.is_visible("text=Logistique, Qualité"))
    page.goto(BASE + "/"); logout(page)

    print("== Compte modifié : connexion + changement de mot de passe ==")
    login(page, "n.nadine", MDP_NADINE)
    check("le compte modifié se connecte avec le NOUVEAU identifiant et mot de passe", page.is_visible("text=Employé"))
    page.wait_for_selector("text=21 j. restants", timeout=8000)
    check("employée créée avec 3 ans d'ancienneté et un enfant de 4 ans : solde de 21 jours attribué automatiquement", True)
    check("employée : solde de congé de maternité de 90 jours (sans condition d'ancienneté)", page.is_visible("text=90 j. restants"))
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    options = [o.inner_text() for o in page.query_selector_all("form select option")]
    check("employée (F) : « Congé de maternité » proposé", any("maternité" in o for o in options))
    check("employée (F) : « Congé de paternité » NON proposé", not any("paternité" in o for o in options))
    check("plus de « Congé sans solde » ni de « Congé payé » dans la liste des types",
          not any(("sans solde" in o) or ("payé" in o) for o in options))

    print("== EMPLOYÉE : congé de maternité (1, 2 ou 3 mois ; 3 mois par an au total) ==")
    D1 = datetime.date(jour.year + 1, 3, 2)     # dates fixes l'année suivante : jamais de chevauchement
    D2 = datetime.date(jour.year + 1, 7, 1)
    D3 = datetime.date(jour.year + 1, 10, 1)
    PIECE = [{"name": "certificat_grossesse.png", "mimeType": "image/png", "buffer": PNG_1X1}]

    def duree_active(m):
        return not page.locator(f"input[name=duree_maternite][value='{m}']").is_disabled()

    page.select_option("form select", label="Congé de maternité")
    check("maternité : un seul champ date (la date de fin n'est pas saisie)", page.locator("input[type=date]").count() == 1)
    check("maternité : choix de 1, 2 ou 3 mois (plus de formules autour du terme)",
          page.locator("input[name=duree_maternite]").count() == 3
          and all(page.is_visible(f"label:has-text('{m} mois')") for m in (1, 2, 3))
          and not page.is_visible("text=avant le terme"))
    page.fill("input[type=date]", D1.isoformat())
    page.wait_for_timeout(500)
    check("maternité : au départ les 3 durées sont disponibles", all(duree_active(m) for m in (1, 2, 3)))
    for m in (1, 2, 3):
        page.locator(f"input[name=duree_maternite][value='{m}']").check()
        fin_m = D1 + datetime.timedelta(days=30 * m - 1)
        zone = page.locator("fieldset.choix").inner_text()
        check(f"{m} mois : fin {fr(fin_m)}, reprise {fr(retour_apres(fin_m))}, {30 * m} jours décomptés calculés par le système",
              fr(fin_m) in zone and fr(retour_apres(fin_m)) in zone and f"{30 * m} jours décomptés" in zone)
    page.locator("input[name=duree_maternite][value='1']").check()
    page.set_input_files("input[type=file]", files=PIECE)
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=En attente — Manager", timeout=10000)
    check("maternité : demande de 1 mois soumise", True)
    check("historique : 30 jours calendaires décomptés et période de 30 jours",
          page.is_visible("tr:has-text('Congé de maternité'):has-text('30 (calendaires)')")
          and page.is_visible(f"text={D1.isoformat()} → {(D1 + datetime.timedelta(days=29)).isoformat()}"))
    page.click("tr:has-text('Congé de maternité') >> text=Détails")
    check("détails : durée et date de reprise affichées",
          page.is_visible("text=Durée : 1 mois")
          and page.is_visible(f"text=reprise le {fr(retour_apres(D1 + datetime.timedelta(days=29)))}"))

    page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé de maternité")
    page.fill("input[type=date]", D2.isoformat()); page.wait_for_timeout(700)
    check("après 1 mois pris : il reste les options 1 mois et 2 mois (3 mois grisé)",
          duree_active(1) and duree_active(2) and not duree_active(3))
    page.locator("input[name=duree_maternite][value='2']").check()
    page.set_input_files("input[type=file]", files=PIECE)
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=60 (calendaires)", timeout=10000)
    check("maternité : 2 mois acceptés après 1 mois (total 3 mois)", page.is_visible("tr:has-text('Congé de maternité'):has-text('60 (calendaires)')"))

    page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé de maternité")
    page.fill("input[type=date]", D3.isoformat()); page.wait_for_timeout(700)
    check("après 1 + 2 mois : plus aucune durée disponible, message « plus disponible cette année »",
          not any(duree_active(m) for m in (1, 2, 3)) and page.is_visible("text=plus disponible cette année"))
    check("plus de maternité : le bouton « Soumettre » est désactivé", page.is_disabled("button:has-text('Soumettre la demande')"))
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    page.goto(BASE + "/mon-compte"); page.wait_for_selector("text=Changer mon mot de passe", timeout=8000)
    page.get_by_label("Mot de passe actuel").fill(MDP_NADINE)
    page.get_by_label("Nouveau mot de passe").fill("AutreMotDePasse#77")
    page.click("text=Mettre à jour"); page.wait_for_selector("text=Mot de passe mis à jour", timeout=8000)
    check("changement de mot de passe par l'utilisateur", True)
    page.goto(BASE + "/"); logout(page)
    login(page, "n.nadine", "AutreMotDePasse#77")
    check("reconnexion avec le nouveau mot de passe", True)
    logout(page)

    print("== EMPLOYÉE de moins d'un an (c.recrue) : pas de solde, pas de congé annuel ==")
    login(page, "c.recrue")
    page.wait_for_selector("text=moins d’un an", timeout=8000)
    check("tableau de bord : message « moins d'un an d'ancienneté »", True)
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé annuel")
    page.wait_for_selector("text=pas encore", timeout=8000)
    check("congé annuel choisi : message d'information affiché",
          page.is_visible("form >> text=pas encore") or page.is_visible("text=pas encore"))
    check("congé annuel : bouton « Soumettre » désactivé", page.is_disabled("button:has-text('Soumettre la demande')"))
    page.select_option("form select", label="Congé maladie")
    page.wait_for_timeout(300)
    check("congé maladie (sans décompte de solde) : message disparu et bouton actif",
          not page.is_visible("text=pas encore") and not page.is_disabled("button:has-text('Soumettre la demande')"))
    page.select_option("form select", label="Congé de maternité")
    page.fill("input[type=date]", datetime.date(jour.year + 1, 3, 2).isoformat())
    page.locator("input[name=duree_maternite][value='2']").check()
    page.set_input_files("input[type=file]", files=[{"name": "certificat.png", "mimeType": "image/png", "buffer": PNG_1X1}])
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=En attente — Manager", timeout=10000)
    check("recrue (< 1 an) : peut demander un congé de maternité de 2 mois (pas de condition d'ancienneté)", True)
    page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé de maternité")
    page.fill("input[type=date]", datetime.date(jour.year + 1, 9, 1).isoformat()); page.wait_for_timeout(700)
    check("après 2 mois pris : la seule option restante est 1 mois (2 et 3 mois grisés)",
          not page.locator("input[name=duree_maternite][value='1']").is_disabled()
          and page.locator("input[name=duree_maternite][value='2']").is_disabled()
          and page.locator("input[name=duree_maternite][value='3']").is_disabled())
    logout(page)

    print("== Règles métier dans l'interface ==")
    login(page, "e.employe")
    page.goto(BASE + "/mes-demandes"); page.click("text=+ Nouvelle demande")
    page.select_option("form select", label="Congé annuel")
    page.fill("input[type=date] >> nth=0", ouvre(1).isoformat())
    page.fill("input[type=date] >> nth=1", ouvre(1).isoformat())
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=délai minimum", timeout=8000)
    check("demande trop proche refusée, message visible : délai de 30 j propre au type « Congé annuel »",
          page.is_visible("text=30 jour(s)") and page.is_visible("text=« Congé annuel »"))
    page.fill("input[type=date] >> nth=0", ouvre(40).isoformat())
    page.fill("input[type=date] >> nth=1", ouvre(41).isoformat())
    page.click("text=Soumettre la demande"); page.wait_for_selector("text=En attente — Manager", timeout=10000)
    page.once("dialog", lambda d: d.accept())
    page.click("button:has-text('Annuler') >> nth=0"); page.wait_for_selector("text=Annulée", timeout=8000)
    check("l'employé annule une demande en cours", True)
    page.close()

    print("== RH : cartes du tableau de bord cliquables et listes détaillées ==")
    page = nouveau_contexte(browser)
    login(page, "r.rh")
    page.wait_for_selector(".carte-lien", timeout=8000)
    check("tableau de bord RH : les 3 cartes sont des liens", page.locator("a.carte-lien").count() == 3)
    page.click("a.carte-lien >> nth=0")
    page.wait_for_url("**/rh/demandes-en-attente", timeout=8000)
    page.wait_for_selector("text=Niveau 1 — Chef de département", timeout=8000)
    check("« Demandes en attente » : liste des demandes par niveau de validation",
          page.is_visible("text=Niveau 1 — Chef de département") and page.is_visible("text=Niveau 2 — Direction Générale"))
    check("liste : demande d'Eric Talla et de Nadine Nkou avec département et type",
          page.is_visible("tr:has-text('Eric Talla'):has-text('Production'):has-text('Congé annuel')")
          and page.is_visible("tr:has-text('Nadine Nkou'):has-text('Production'):has-text('Congé de maternité')"))
    check("liste : niveau de validation affiché (Manager en attente, Direction à venir)",
          page.is_visible("tr:has-text('Nadine Nkou') >> text=1. Manager — en attente")
          and page.is_visible("tr:has-text('Nadine Nkou') >> text=2. Direction — à venir"))
    page.click("tr:has-text('Nadine Nkou') >> text=Voir la demande")
    page.wait_for_url(re.compile(r".*/demandes/\d+$"), timeout=8000)
    page.wait_for_selector("text=Historique des validations", timeout=8000)
    check("« Voir la demande » ouvre le détail de la demande (maternité : durée et reprise)",
          page.is_visible("text=Durée :") and page.is_visible("text=reprise le"))
    page.goto(BASE + "/rh/dashboard"); page.wait_for_selector("a.carte-lien", timeout=8000)
    page.click("a.carte-lien >> nth=1")
    page.wait_for_url("**/rh/employes-sans-conge-annuel", timeout=8000)
    page.wait_for_selector("text=Employés éligibles sans congé annuel validé", timeout=8000)
    check("« Salariés sans congé annuel » : employée éligible listée avec son département et son droit (21 j)",
          page.is_visible("tr:has-text('Nadine Nkou'):has-text('Production'):has-text('21 j')"))
    check("liste : l'employé ayant un congé annuel validé (Eric Talla) n'y figure pas", not page.is_visible("tr:has-text('Eric Talla')"))
    check("liste : l'employée de moins d'un an (c.recrue) n'y figure pas (non éligible)", not page.is_visible("td:has-text('Mvondo')"))
    page.goto(BASE + "/rh/dashboard"); page.wait_for_selector("a.carte-lien", timeout=8000)
    page.click("a.carte-lien >> nth=2")
    page.wait_for_url("**/rh/alertes-solde", timeout=8000)
    page.wait_for_selector("text=Alertes de solde faible", timeout=8000)
    check("« Alertes solde faible » redirige vers la liste des soldes concernés (employé, département, type, seuil)", True)
    page.close()

    print("== LIEN PROFOND : retour vers la page demandée après connexion ==")
    page = nouveau_contexte(browser)
    page.goto(BASE + "/rh/dashboard"); page.wait_for_url("**/connexion", timeout=8000)
    page.fill("input[type=text]", "r.rh"); page.fill("input[type=password]", MDP); page.click("button[type=submit]")
    page.wait_for_selector("text=Effectifs et congés par département", timeout=10000)
    check("non connecté sur /rh/dashboard -> connexion RH -> retour sur /rh/dashboard", page.url.endswith("/rh/dashboard"))
    page.close()
    page = nouveau_contexte(browser)
    page.goto(BASE + "/admin/utilisateurs"); page.wait_for_url("**/connexion", timeout=8000)
    page.fill("input[type=text]", "e.employe"); page.fill("input[type=password]", MDP); page.click("button[type=submit]")
    page.wait_for_url("**/acces-refuse", timeout=10000)
    check("lien profond admin + connexion employé -> /acces-refuse (RBAC respecté)", page.url.endswith("/acces-refuse"))
    browser.close()

print()
print("Réponses HTTP en erreur observées :")
for r in sorted(set(reponses_en_erreur)):
    print(f"   {reponses_en_erreur.count(r)} × {r}" + ("   (provoquée volontairement)" if r in ATTENDUES else "   <-- INATTENDUE"))
inattendues = [r for r in reponses_en_erreur if r not in ATTENDUES]
# Chaque réponse volontaire doit apparaître exactement le nombre de fois prévu (sinon le test n'a pas fait ce qu'on croit).
manquantes_ou_multiples = [a for a, n in ATTENDUES.items() if reponses_en_erreur.count(a) != n]
print("Exceptions JavaScript :", len(erreurs_js))
for e in erreurs_js[:8]:
    print("   ", e)
reussis = sum(resultats)
print(f"BILAN : {reussis}/{len(resultats)} contrôles réussis")
ok = reussis == len(resultats) and not inattendues and not manquantes_ou_multiples and not erreurs_js
sys.exit(0 if ok else 1)
