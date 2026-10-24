# Gestionnaire de Congés — Delifood Agro-Industry

Backend de l'application de gestion des congés, développé à partir du
**cahier des charges v1.1** (Yves Eteme, stagiaire Software Engineering,
Delifood Agro-Industry) et de l'analyse conceptuelle UML qui en a été tirée.

Stack : **Django 6 / Django REST Framework / SQLite (dev) ou MySQL (prod)**,
authentification **JWT**. Correspond au circuit « React.js / Django / MySQL »
visé par le cahier des charges. Le frontend React se trouve dans le dossier
frère `../frontend` (voir son README) ; l'**admin Django** (`/admin/`) reste
disponible comme recours.

## 1. Démarrage rapide

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo        # données de démonstration (voir §3)
python manage.py createsuperuser  # optionnel si vous ne voulez pas utiliser a.admin
python manage.py runserver
```

L'API est alors servie sur `http://127.0.0.1:8000/api/` et l'admin sur
`http://127.0.0.1:8000/admin/`.

Copier `.env.example` en `.env` pour personnaliser la configuration
(secret key, base MySQL, SMTP réel). Le fichier `.env` est lu
automatiquement au démarrage ; une vraie variable d'environnement prend
toujours le pas sur le fichier. Sans `.env`, le projet démarre tel quel
avec SQLite et un envoi d'e-mails simulé en console.

### Basculer vers MySQL

Une première version du projet (19 tests) a été validée sur MariaDB 10.11
(migrations, `seed_demo`, tests), sans modification de code — seules des
variables d'environnement changent. La suite actuelle (219 tests) n'a été
exécutée que sur SQLite : relancer `manage.py test conges` sur votre base
MySQL avant de déployer.

1. **Installer un serveur MySQL/MariaDB** s'il n'est pas déjà présent :
   - Ubuntu/Debian : `sudo apt install mariadb-server libmysqlclient-dev build-essential pkg-config`
   - macOS (Homebrew) : `brew install mysql pkg-config`
   - Windows : installeur officiel MySQL Community Server.
   Démarrer le service (`sudo service mariadb start` sur Linux, ou via les
   Services Windows / `brew services start mysql` sur macOS).

2. **Créer la base et un utilisateur dédié** (adapter le mot de passe) :
   ```sql
   CREATE DATABASE gestionnaire_conges CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'conges_user'@'localhost' IDENTIFIED BY 'change-moi';
   GRANT ALL PRIVILEGES ON gestionnaire_conges.* TO 'conges_user'@'localhost';
   -- Indispensable pour pouvoir lancer `manage.py test` (Django crée une
   -- base de test nommée test_<NAME> à la volée) :
   GRANT ALL PRIVILEGES ON `test_gestionnaire_conges`.* TO 'conges_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. **Installer le driver Python** : `pip install mysqlclient` (déjà dans
   `requirements.txt`). Nécessite les en-têtes de dev installés à l'étape 1.

4. **Configurer `.env`** (copié depuis `.env.example`) avec `DB_ENGINE=mysql`
   et les identifiants ci-dessus.

5. **Relancer** `python manage.py migrate` puis `python manage.py seed_demo` —
   tout fonctionne à l'identique de SQLite, simplement sur MySQL.

## 2. Lancer les tests

```bash
python manage.py test conges          # 219 tests (logique métier + API + RBAC)

# Avec couverture (exigence CDC §8/§14.2 : ≥ 30 % sur le code critique) :
pip install coverage
coverage run --source='accounts,conges' manage.py test conges
coverage report -m    # 97 % sur accounts+conges au moment de la livraison
```

## 3. Comptes de démonstration (`seed_demo`)

| Compte | Rôle | Mot de passe |
| --- | --- | --- |
| `e.employe` | Employé (département Production) | `Conges#2026` |
| `j.manager` | Manager / chef de département (dirige Production) | `Conges#2026` |
| `p.directeur` | Direction Générale (DGA) | `Conges#2026` |
| `r.rh` | Responsable RH | `Conges#2026` |
| `a.admin` | Administrateur (superuser Django admin) | `Conges#2026` |
| `c.recrue` | Employée **de moins d'un an** d'ancienneté (Production) — sans solde, donc sans congé annuel | `Conges#2026` |

La commande crée aussi : les types de congés courants (congé annuel,
maladie, paternité, maternité), les jours fériés camerounais
2026, et un solde de 18 jours pour l'employé de démo (plus d'un an d'ancienneté).
`c.recrue` n'a volontairement aucun solde.

## 4. Le workflow implémenté — circuit à DEUX niveaux

```
BROUILLON → EN_ATTENTE_MANAGER → EN_ATTENTE_DIRECTION → VALIDEE
                     ↘ REFUSEE               ↘ REFUSEE
```

Chef de département (1er niveau) → Direction Générale / DQN·DU·DAF·DGA·DG
(2e niveau, décision finale). La RH **ne valide plus** les demandes dans
cette version du cahier des charges : elle paramètre les types de congés,
gère les jours fériés, et dispose d'un tableau de bord — voir §7.

> **Remarque sur une incohérence du cahier des charges v1.1** : les
> sections 2.2, 4.1, 5, 6.1-6.3 et 7 décrivent sans ambiguïté un circuit à
> **deux** niveaux (Manager → Direction Générale, validation finale).
> Quelques sections n'ont cependant pas été mises à jour en cohérence
> lors de la dernière révision : le tableau de planning §11.4 parle encore
> d'un « workflow à trois niveaux (… → RH) », le critère de recette §14.1
> mentionne « les trois niveaux du circuit », et le glossaire §16.1 décrit
> le Directeur comme « intermédiaire entre le chef de département et la
> RH ». Ce backend suit la version **deux niveaux**, qui est la décision
> dominante et la plus récente du document ; à confirmer avec l'encadrant
> de stage / la RH avant la soutenance, et à corriger dans le cahier des
> charges lui-même.

## 5. Correspondance avec le cahier des charges

| Besoin (CDC) | Implémenté dans |
| --- | --- |
| §7 Authentification + rôles (RBAC) | `accounts.Utilisateur` (rôle + fonction de direction), JWT (`/api/auth/token/`) |
| §7 Gestion des types de congés | `conges.TypeConge` + `TypeCongeViewSet` |
| §7 Workflow de validation à deux niveaux | `conges.services.soumettre_demande` / `valider_niveau` + `DemandeCongeViewSet` |
| §7 Vérification des règles métier | `DemandeConge.verifier_regles_metier` (solde, délai, chevauchement, justificatif) |
| §7 Gestion des soldes | `conges.SoldeConge` + `SoldeConge.mettre_a_jour` |
| §6.4 Tableau de bord RH | `DashboardRHView` (`/api/dashboard/rh/`) |
| §2.2 Export Comptabilité | `ExportDemandesCSVView` (`/api/export/demandes.csv`) — **demandes validées uniquement**, CSV seul (pas d'Excel ni de PDF) |
| §6.4 Jours fériés / fermetures | `conges.JourFerie` + `JourFerieViewSet` |
| §7 Traçabilité / journal d'audit | `conges.JournalAudit`, peuplé automatiquement par la couche service |
| §6.6 Notifications à chaque étape | `conges.Notification` + envoi e-mail (backend console en dev) |
| §6.5 Comptes utilisateurs (Administrateur) | `UtilisateurViewSet` (création réservée au rôle Administrateur) |
| §6.5 Délai minimum / seuils d'alerte configurables | `conges.ParametresSysteme` + `ParametresSystemeView` (valeurs par défaut) et `TypeConge.delai_minimum_jours` / `seuil_alerte_jours` (par type, Admin) |
| §8 Couverture de tests ≥ 30 % | 219 tests (voir §2 pour la couverture) |

## 6. Principaux endpoints API

Toutes les routes (sauf `/api/auth/token/`) exigent l'en-tête
`Authorization: Bearer <access_token>`.

| Méthode & route | Rôle(s) | Description |
| --- | --- | --- |
| `POST /api/auth/token/` | public | Connexion (username + password) → `access` / `refresh` |
| `POST /api/auth/token/refresh/` | — | Renouvelle un access token |
| `GET /api/me/` | tous | Profil connecté + soldes de l'année en cours |
| `POST /api/me/mot-de-passe/` | tous | Changer son mot de passe (ancien mot de passe requis) |
| `GET/POST /api/demandes/` | Employé (création), rôle-dépendant (liste) | Mes demandes / soumission |
| `POST /api/demandes/{id}/annuler/` | propriétaire, RH, Admin | Annulation avant validation |
| `POST /api/demandes/{id}/valider-manager/` | Manager du département concerné | Décision 1er niveau |
| `POST /api/demandes/{id}/valider-direction/` | Direction Générale | Décision 2e niveau (finale) |
| `GET/POST /api/types-conge/`, `/api/jours-feries/` | lecture : tous ; écriture : RH/Admin | Paramétrage |
| `GET /api/soldes/` | soi-même, ou RH/Admin (tous) | Soldes de congés |
| `GET /api/dashboard/rh/?annee=` | RH, Admin | Indicateurs clés (`demandes_en_attente`, `salaries_sans_conge_annuel`, `alertes_solde_faible`) + tableau par département : `effectif`, `employes`, `eligibles_conge_annuel`, `ont_pris_conge`, `jours_conges_valides` (et `totaux`) |
| `GET /api/dashboard/rh/demandes-en-attente/` | RH, Admin | Demandes en attente (tous niveaux) avec niveau de validation actuel et historique des décisions |
| `GET /api/dashboard/rh/employes-sans-conge-annuel/?annee=` | RH, Admin | Employés éligibles (≥ 1 an) sans congé annuel validé dans l'année : nom, matricule, département, droit annuel, jours restants |
| `GET /api/dashboard/rh/alertes-solde/?annee=` | RH, Admin | Soldes sous leur seuil d'alerte : employé, département, type, jours acquis/restants, seuil appliqué |
| `GET /api/export/demandes.csv?annee=` | RH, Admin | Export CSV (Comptabilité) — uniquement les demandes **validées** |
| `GET /api/journal-audit/` | RH, Admin | Journal d'audit |
| `GET/PUT /api/parametres-systeme/` | lecture RH/Admin ; écriture Admin | Délai minimum, seuil d'alerte |
| `GET/POST/PUT/PATCH/DELETE /api/utilisateurs/` | lecture : Manager, Direction, RH, Admin (pas les Employés) ; écriture et suppression : Admin | Comptes. Création : `sexe` (M/F) obligatoire, `telephone` facultatif. Modification (PATCH) : identifiant, prénom, nom, e-mail, téléphone, matricule, sexe, rôle, département, `departements_supervises`, statut, mot de passe (optionnel). Suppression : voir « Règles ajoutées » |
| `POST /api/utilisateurs/{id}/definir-mot-de-passe/` | Admin | Réinitialiser le mot de passe d'un compte |
| `GET /api/departements/` (+ écriture) | lecture : tous ; création/modification : RH/Admin ; suppression : Admin | Organisation : chef (`responsable`, 1er niveau) et `directeur` superviseur (2e niveau) |
| `GET /api/equipe/absences/` (`?periode=en_cours\|a_venir`) | Manager | Collaborateurs de son département en congé (validé) ou en congé prochainement : nom, rôle, e-mail, téléphone, date de départ, date de retour |
| `GET /api/demandes/{id}/justificatif/` | employé concerné, Manager du département, Direction compétente, RH, Admin | Téléchargement authentifié du justificatif (aucune URL `/media/` publique) |
| `GET /api/notifications/` (`?lu=false`) | tous (les siennes) | Notifications |
| `POST /api/notifications/{id}/marquer_lu/`, `POST /api/notifications/tout-marquer-lu/` | tous (les siennes) | Marquer comme lues |

### Matrice RBAC (appliquée côté API, doublée par les gardes du frontend)

| Rôle | Peut faire |
| --- | --- |
| Employé | Créer/annuler ses demandes, consulter ses soldes et notifications, changer son mot de passe. Ne voit ni l'annuaire des utilisateurs, ni les demandes des autres. |
| Manager | Valider/refuser (1er niveau) les demandes de son département, voir son équipe et la liste des absences de son département, consulter les justificatifs. |
| Directeur (DQN/DU/DAF/DGA/DG) | Décision finale (2e niveau) pour les départements qu'il supervise (plusieurs possibles) et pour ceux sans directeur affecté ; le solde est débité à cette étape. Consulte les justificatifs. |
| RH | Types de congés, jours fériés, tableau de bord, export CSV, journal d'audit, lecture de toutes les demandes. Ne valide pas. |
| Administrateur | Créer, modifier et supprimer les comptes (identifiant, prénom, nom, e-mail, téléphone, matricule, sexe, rôle, département, mot de passe, activation), supprimer les départements, paramètres système, **délai minimum et seuil d'alerte propres à chaque type de congé**. |

### Règles ajoutées dans cette version

- **Sexe (M/F)** : champ obligatoire à la création d'un compte. Chaque type de
  congé peut être « réservé à un sexe » (`reserve_a_sexe`) : par défaut
  *Congé de maternité* → F, *Congé de paternité* → M. Une demande d'un type
  réservé à l'autre sexe est refusée (HTTP 400) par l'API, et l'interface
  ne propose pas ces types. Les types dont le libellé contient « maternité »
  ou « paternité » sont réservés automatiquement par la migration sur une
  base existante ; la RH peut réserver tout autre type. Les comptes
  antérieurs sans sexe renseigné ne peuvent pas prendre un type réservé tant
  que l'Administrateur ne l'a pas renseigné.
- **Directeur multi-départements** : un directeur peut superviser plusieurs
  départements (`Departement.directeur`) ; un département n'a qu'un directeur
  superviseur. Un directeur ne voit et ne traite que les demandes de ses
  départements, plus celles des départements **sans** directeur affecté (ou
  des employés sans département), pour qu'aucune demande ne reste sans
  décideur. Affectation possible depuis le compte du directeur ou depuis la
  page Départements. Si un compte perd son rôle de directeur (ou de manager),
  ses rattachements sont libérés.
- **Justificatifs** : PDF, PNG ou JPEG de 5 Mo maximum, contenu vérifié. Ils
  sont visibles par les deux niveaux de validation (Manager puis Direction),
  ainsi que par l'employé, la RH et l'Administrateur, via un endpoint
  authentifié qui applique le périmètre de chaque rôle.
- **Téléphone** : champ facultatif sur le compte (7 à 20 caractères : chiffres,
  espaces, `+`, `-`, `.` ou parenthèses). Visible dans l'annuaire, l'équipe,
  « Mon compte » et la liste des absences.
- **Suppression d'un employé (Admin)** : supprime définitivement le compte
  **et** ses demandes, soldes et notifications ; le journal d'audit conserve
  un instantané du compte supprimé et les décisions qu'il avait prises restent
  sur les demandes des autres (auteur affiché comme inconnu). Un administrateur
  ne peut pas supprimer son propre compte. Supprimer un manager libère son
  département ; supprimer un directeur détache ses départements. Pour
  conserver l'historique, préférer la désactivation du compte.
- **Suppression d'un département (Admin)** : refusée tant que des utilisateurs
  (hors son chef) y sont rattachés — il faut d'abord les réaffecter, sinon
  leurs demandes n'auraient plus de manager. Le chef et le directeur
  superviseur sont simplement détachés.
- **Absences de l'équipe (Manager)** : uniquement les congés **validés**, des
  collaborateurs actifs de son département, en cours ou à venir. La date de
  retour est le premier jour de travail après le dernier jour d'absence
  (week-ends et jours fériés exclus). Le type de congé et le motif ne sont pas
  exposés (vie privée : maladie, maternité…).
- **Date d'entrée et ancienneté** : pour un compte de rôle *Employé*, la date
  d'entrée à l'usine (`date_embauche`) est **obligatoire** à la création (et
  si l'on passe un compte au rôle Employé) ; elle ne peut pas être future.
  L'ancienneté est le nombre d'années **révolues** (`Utilisateur.anciennete_annees()`).
- **Droit au congé annuel (18 ou 21 jours)** : à partir de **1 an révolu**
  d'ancienneté, l'employé a droit à **18 jours** de congé annuel par an. Pour une
  **employée** (sexe F), à la création du compte, on indique si elle a un enfant
  (`a_enfant`) et, si oui, l'âge de son dernier enfant (`age_dernier_enfant`,
  en années) : **6 ans ou moins → 21 jours**, **plus de 6 ans → 18 jours** (la
  majoration ne s'applique que si elle a l'ancienneté requise). La réponse est
  obligatoire pour une employée ; pour un homme ou un autre rôle, ces champs
  sont vides. Le plafond du type de congé n'intervient pas dans ce calcul.
  Le solde de l'année est créé automatiquement : à la
  création/modification du compte, à la connexion (`/api/auth/me/`), à la
  soumission d'une demande, et par la commande
  `python manage.py synchroniser_soldes` (à planifier une fois par jour, par
  exemple avec cron, pour attribuer le solde au jour anniversaire). Un solde
  intact (sans aucune demande) est réaligné si le compte change (date d'entrée,
  enfant…) ; un solde déjà utilisé n'est jamais modifié. L'âge du dernier enfant
  est une valeur saisie : il n'est pas mis à jour automatiquement d'une année à l'autre.
- **Pas de solde, pas de congé annuel** : un employé sans solde pour l'année de
  la demande ne peut pas poser un congé annuel. L'API répond 400 avec un message
  explicite (pas de date d'entrée / moins d'un an d'ancienneté / aucun solde).
  Les types sans décompte (maladie, paternité) restent possibles. Le « Congé sans solde »
  a été supprimé (la migration `conges.0005` le retire s'il n'est référencé par
  aucune demande ; sinon il est conservé pour ne pas perdre l'historique) et « Congé payé »
  est devenu « Congé annuel ».
- **Congé de maternité** (type `est_maternite`, réservé aux femmes) : **3 mois
  par an** (90 jours calendaires, jours ouvrés + non ouvrés), décomptés d'un solde
  de maternité de 90 jours attribué à toute employée active, sans condition
  d'ancienneté. L'employée choisit la **durée** de chaque congé : **1, 2 ou 3 mois**
  (`duree_maternite_mois`, 30 jours décomptés par mois), et peut le prendre en
  plusieurs fois dans la limite du solde de l'année du départ :
  après **1 mois**, il reste les options **1 mois et 2 mois** ; après **2 mois**,
  il ne reste que **1 mois** ; après **3 mois** (ou 1 + 2, 1 + 1 + 1…), le congé de
  maternité n'est **plus disponible cette année**. Les demandes en attente et
  validées comptent ; les demandes refusées ou annulées libèrent leurs mois.
  L'employée saisit sa **date de départ** : le système calcule la date de fin
  (départ + 30 × mois − 1 jours) et la **date de retour** (premier jour ouvré suivant).
  `GET /api/soldes/` expose pour chaque solde `jours_engages` (demandes en attente),
  `jours_disponibles` et, pour la maternité, `mois_disponibles` (ex. `[1, 2]`).
  Le justificatif reste obligatoire. Le débit du solde (`nb_jours_decomptes`) a lieu à
  la validation finale de la Direction.
- **Tableau de bord RH cliquable** : les cartes « Demandes en attente »,
  « Salariés sans congé annuel validé cette année » et « Alertes solde faible »
  ouvrent chacune une liste détaillée (`/rh/demandes-en-attente`,
  `/rh/employes-sans-conge-annuel`, `/rh/alertes-solde`).
- **Notifications** : chaque notification pointe vers sa demande ; dans
  l'interface, un clic ouvre la page `/demandes/:id` (Manager, Directeur,
  Employé…), où le Manager ou le Directeur peut décider directement. L'API ne
  renvoie la demande qu'aux personnes de son périmètre (sinon 404).
- **Indicateurs RH par département** : effectif total, nombre d'employés,
  employés éligibles au congé annuel (≥ 1 an), employés ayant pris au moins un
  congé validé dans l'année, jours validés. Les comptes sans département
  apparaissent sur une ligne « Sans département ».
- **Délai minimum et seuil d'alerte par type de congé** : chaque type (défini par
  la RH) peut avoir son propre `delai_minimum_jours` (délai entre la soumission
  et le début du congé) et son propre `seuil_alerte_jours` (alerte « solde
  faible » de la RH). Ces deux champs sont **réservés à l'Administrateur**
  (`PATCH /api/types-conge/{id}/` ; la RH reçoit un 400 si elle tente de les
  modifier, mais garde la main sur le reste de la définition du type). Un champ
  vide = valeur par défaut des paramètres système. L'API renvoie aussi les
  valeurs *effectives* (`delai_minimum_effectif`, `seuil_alerte_effectif`).
  Chaque modification est inscrite au journal d'audit. Page : `/admin/types-conge`.
- **Export** : CSV uniquement (l'export Excel a été retiré) ; il ne contient que
  les demandes au statut *Validée* (brouillons, demandes en attente, refusées
  et annulées sont exclus).
- **Garde-fous** : le dernier administrateur actif ne peut être ni
  rétrogradé ni désactivé ; les modifications de comptes sont inscrites au
  journal d'audit (sans le mot de passe).

> **Mise à jour d'une base existante** : lancer `python manage.py migrate`
> (migrations `accounts.0002` à `0004` et `conges.0002` à `0006`), puis renseigner le sexe
> et la date d'entrée des comptes existants depuis l'écran Utilisateurs (sans date
> d'entrée, un employé n'a pas de solde). La migration `conges.0003` ajoute les deux seuils
> par type (vides = valeurs par défaut, donc aucun changement de comportement) ;
> `python manage.py synchroniser_soldes` attribue ensuite les soldes manquants.
> Pour les employées existantes, renseigner « a un enfant / âge du dernier enfant » depuis l'écran
> Utilisateurs (sans réponse, le droit reste de 18 jours). La migration `conges.0005` renomme
> « Congé payé » en « Congé annuel », supprime « Congé sans solde » s'il est inutilisé et
> configure le congé de maternité (décompte de solde, 90 jours) ; `conges.0006` remplace les
> anciennes « formules » autour du terme par la durée en mois (les demandes existantes deviennent des demandes de 3 mois).

## 7. Hors périmètre de cette itération (pistes suivantes)

- **Mise en production** — passer `DJANGO_DEBUG=0`, définir une vraie
  `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS`,
  utiliser MySQL, servir `npm run build` du frontend derrière Nginx avec un
  proxy `/api` et `/media`, et activer HTTPS. Les jetons JWT sont stockés
  dans le `localStorage` du navigateur (compromis courant, sensible au XSS) ;
  un cookie HttpOnly serait l'étape suivante.
- **Export Excel / PDF** — seul le CSV est proposé (l'Excel a été retiré à la demande) ; le PDF (§2.2) reste à faire.
- **Envoi SMTP réel** — backend console par défaut ; configurer les
  variables `EMAIL_*` dans `.env` pour un envoi réel.
- **MySQL** — validé sur MariaDB 10.11 avec la première version (19 tests) ;
  à revérifier avec la suite actuelle ; voir « Basculer vers MySQL » ci-dessus.
- **Règles d'acquisition mensuelle des droits** — `TypeConge.calculer_droits_acquis`
  retourne actuellement le plafond annuel ; l'acquisition mensuelle
  progressive (1,5 j/mois) reste à affiner avec la RH.
- **Relances automatiques / seuils d'alerte sur délai de traitement**
  (§11.4, risques) — paramètre `ParametresSysteme.seuil_alerte_solde_jours`
  posé, mais pas encore de tâche planifiée (ex. Celery) pour les relances.

## 8. Structure du projet

```
gestionnaire_conges/
├── config/              # settings, urls racine
├── accounts/            # Utilisateur (RBAC), Departement
├── conges/               # TypeConge, SoldeConge, DemandeConge, Validation,
│                         # Notification, JournalAudit, JourFerie, services,
│                         # tests/ (unitaires + intégration API)
├── manage.py
├── requirements.txt
├── .env.example
└── README.md             # ce fichier
```
