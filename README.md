# Gestionnaire de Congés — Delifood Agro-Industry

Application web de gestion des congés (cahier des charges v1.1, circuit de
validation à deux niveaux : Manager → Direction).

```
gestionnaire_conges/   Backend Django / DRF / JWT   → README.md dedans
frontend/              Frontend React 19 / Vite     → README.md dedans
```

## Spécifications (Spec-Driven Development)
Le projet est documenté selon la méthode Spec Kit : `.specify/memory/constitution.md` (principes), puis `specs/` — un dossier par fonctionnalité (`spec.md` avec exigences numérotées et traçabilité vers les tests, `tasks.md`) et `specs/000-fondations/` (plan, recherche, modèle de données, contrats d'API, démarrage rapide). Index et ordre de lecture : `specs/README.md`.

## Lancer en local

```bash
# Terminal 1 — API
cd gestionnaire_conges
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # mysqlclient requiert les en-têtes MySQL ;
                                    # commentez-le dans requirements.txt si vous restez sur SQLite
python manage.py migrate
python manage.py seed_demo
python manage.py runserver          # http://127.0.0.1:8000

# Terminal 2 — interface
cd frontend
npm install
npm run dev                         # http://localhost:5173
```

Connexion avec `e.employe`, `j.manager`, `p.directeur`, `r.rh` ou `a.admin`
(mot de passe `Conges#2026`).

## Vérifications

- Backend : `python manage.py test conges` (255 tests)
- Frontend : `npm run lint && npm run build`
- Bout en bout : `python3 frontend/e2e/parcours_complet.py` (serveurs lancés)
