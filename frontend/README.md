# Frontend — Gestionnaire de Congés (React)

Interface React 19 (Vite) de l'application, branchée sur l'API Django
(`../gestionnaire_conges`). Authentification JWT, routes protégées par rôle.

## Démarrage

```bash
# 1. Backend (autre terminal) : voir ../gestionnaire_conges/README.md
#    python manage.py migrate && python manage.py seed_demo && python manage.py runserver

# 2. Frontend
npm install
npm run dev          # http://localhost:5173
```

Le serveur de développement relaie `/api` et `/media` vers
`http://127.0.0.1:8000`. Pour viser un autre backend :
`VITE_API_PROXY_TARGET=http://hote:8000 npm run dev`.

Comptes de démonstration (mot de passe `Conges#2026`) : `e.employe`,
`j.manager`, `p.directeur`, `r.rh`, `a.admin`.

## Écrans par rôle (RBAC)

| Rôle | Routes |
| --- | --- |
| Tous | `/` (tableau de bord), `/notifications` (un clic ouvre la demande concernée), `/demandes/:id` (détail d'une demande ; le Manager et le Directeur y décident), `/mon-compte` |
| Employé | `/mes-demandes` |
| Manager | `/validations/manager`, `/equipe`, `/absences` (collaborateurs en congé : coordonnées, départ, retour) |
| Directeur | `/validations/direction` |
| RH | `/rh/dashboard` (effectifs, éligibles au congé annuel et congés pris par département), `/rh/demandes-en-attente`, `/rh/employes-sans-conge-annuel`, `/rh/alertes-solde` (listes ouvertes depuis les cartes du tableau de bord), `/rh/types-conge`, `/rh/jours-feries`, `/rh/export` (CSV, demandes validées uniquement) |
| Administrateur | `/admin/utilisateurs` (création avec date d'entrée pour les employés, modification complète, suppression, tri de l'annuaire par nom, rôle ou département), `/admin/departements` (chef, directeur superviseur, suppression), `/admin/types-conge` (délai minimum et seuil d'alerte par type de congé), `/admin/parametres` (valeurs par défaut) |

`RequireAuth` masque les écrans non autorisés (redirection vers
`/acces-refuse`), mais **la sécurité réelle est côté API** : chaque endpoint
Django vérifie le rôle, le frontend ne fait que refléter ces règles.

## Charte graphique

Couleurs relevées sur le logo « Belles Tomates » : rouge tomate, vert feuille et blanc.
Elles sont définies une seule fois, en variables CSS, en tête de `src/styles/index.css`.
Les teintes exactes du logo (`--rouge-logo`, `--vert-logo`) servent aux aplats décoratifs
(liseré sous l'en-tête, pastille de notifications) ; le texte et les boutons utilisent des
variantes un peu plus foncées (`--rouge`, `--vert`) pour un contraste ≥ 4,5:1 avec le blanc.

## Scripts

- `npm run lint` — oxlint
- `npm run build` — build de production dans `dist/`
- Test de bout en bout : `e2e/parcours_complet.py` (Playwright Python +
  Chromium). Lancer backend (base seedée) et `npm run dev`, puis
  `python3 e2e/parcours_complet.py`. Parcourt les 5 rôles, le circuit à deux
  niveaux, les refus RBAC, la modification de comptes par l'admin, les congés
  réservés à un sexe, le directeur multi-départements, l'ouverture du
  justificatif par le Manager et la Direction, le téléphone, la suppression d'un employé et d'un département, la liste des absences du Manager, le changement de mot de passe
  la date d'entrée et le droit au congé annuel, les notifications qui ouvrent la demande, le tri de l'annuaire, les indicateurs par département et l'export CSV limité aux congés validés et les seuils par type configurés par l'Admin (117 contrôles).

## Production

`npm run build`, servir `dist/` avec Nginx, proxy `/api` et `/media` vers
Django (même origine → pas de CORS). Voir la section « Mise en production »
du README backend.
