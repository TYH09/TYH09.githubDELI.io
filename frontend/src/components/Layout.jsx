import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import RoleBadge from './RoleBadge'

/**
 * Liens de navigation par rôle — reflète le RBAC de l'API : chaque lien
 * correspond à un écran que ce rôle est effectivement autorisé à utiliser
 * côté backend (cf. conges/permissions.py et le CDC §6).
 */
function liensPourRole(role) {
  const accueil = { to: '/', label: 'Tableau de bord' }
  const communs = [
    { to: '/notifications', label: 'Notifications' },
    { to: '/mon-compte', label: 'Mon compte' },
  ]
  const specifiques = {
    EMPLOYE: [{ to: '/mes-demandes', label: 'Mes demandes' }],
    MANAGER: [
      { to: '/validations/manager', label: 'Demandes à valider' },
      { to: '/equipe', label: 'Mon équipe' },
      { to: '/absences', label: 'Absences' },
    ],
    DIRECTEUR: [{ to: '/validations/direction', label: 'Demandes à valider' }],
    RH: [
      { to: '/rh/dashboard', label: 'Indicateurs RH' },
      { to: '/rh/types-conge', label: 'Types de congés' },
      { to: '/rh/jours-feries', label: 'Jours fériés' },
      { to: '/rh/export', label: 'Export' },
    ],
    ADMINISTRATEUR: [
      { to: '/admin/utilisateurs', label: 'Utilisateurs' },
      { to: '/admin/departements', label: 'Départements' },
      { to: '/admin/types-conge', label: 'Types de congés' },
      { to: '/admin/parametres', label: 'Paramètres' },
    ],
  }
  return [accueil, ...(specifiques[role] || []), ...communs]
}

/**
 * Rend les tableaux lisibles sur mobile : recopie le texte de chaque en-tête
 * (<th>) dans un attribut data-label sur les cellules correspondantes. Le CSS
 * (≤ 720 px) affiche alors chaque ligne comme une carte « libellé : valeur ».
 * Un MutationObserver couvre les tableaux affichés après chargement des données.
 */
function etiqueterTableaux(racine) {
  racine.querySelectorAll('table.tableau').forEach((table) => {
    const entetes = []
    table.querySelectorAll('thead th').forEach((th) => {
      const n = parseInt(th.getAttribute('colspan') || '1', 10)
      for (let i = 0; i < n; i += 1) entetes.push(th.textContent.replace(/[▲▼↕⇕↑↓]/g, '').trim())
    })
    if (!entetes.length) return
    table.querySelectorAll('tbody tr').forEach((tr) => {
      let col = 0
      tr.querySelectorAll(':scope > td').forEach((td) => {
        const n = parseInt(td.getAttribute('colspan') || '1', 10)
        if (n === 1 && entetes[col] && td.getAttribute('data-label') !== entetes[col]) {
          td.setAttribute('data-label', entetes[col])
        }
        col += n
      })
    })
  })
}

function useTableauxResponsives(ref) {
  useEffect(() => {
    const racine = ref.current
    if (!racine) return undefined
    etiqueterTableaux(racine)
    const observateur = new MutationObserver(() => etiqueterTableaux(racine))
    observateur.observe(racine, { childList: true, subtree: true })
    return () => observateur.disconnect()
  }, [ref])
}

export default function Layout() {
  const [menuOuvert, setMenuOuvert] = useState(false)
  const contenuRef = useRef(null)
  useTableauxResponsives(contenuRef)
  const { profil, deconnecter } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [notificationsNonLues, setNotificationsNonLues] = useState(0)

  useEffect(() => {
    setMenuOuvert(false) // referme le menu mobile après navigation
  }, [pathname])

  useEffect(() => {
    let annule = false
    api
      .get('/notifications/', { params: { lu: false } })
      .then(({ data }) => {
        if (!annule) setNotificationsNonLues(data.count)
      })
      .catch(() => {})
    return () => {
      annule = true
    }
  }, [pathname]) // recompté à chaque changement de page (ex. après lecture d'une notification)

  function handleDeconnexion() {
    deconnecter()
    navigate('/connexion', { replace: true })
  }

  const liens = liensPourRole(profil.role)

  return (
    <div className="mise-en-page">
      <header className="entete">
        <div className="entete__marque">
          <span className="entete__logo">GC</span>
          <span>Gestionnaire de Congés</span>
        </div>
        <button
          type="button"
          className="entete__burger"
          aria-label="Menu"
          aria-expanded={menuOuvert}
          aria-controls="navigation-principale"
          onClick={() => setMenuOuvert((o) => !o)}
        >
          {menuOuvert ? '✕' : '☰'}
        </button>
        <nav id="navigation-principale" className={'entete__nav' + (menuOuvert ? ' entete__nav--ouvert' : '')}>
          {liens.map((lien) => (
            <NavLink
              key={lien.to}
              to={lien.to}
              end={lien.to === '/'}
              className={({ isActive }) => 'entete__lien' + (isActive ? ' entete__lien--actif' : '')}
            >
              {lien.label}
              {lien.to === '/notifications' && notificationsNonLues > 0 && (
                <span className="pastille">{notificationsNonLues}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className={'entete__utilisateur' + (menuOuvert ? ' entete__utilisateur--ouvert' : '')}>
          <div className="entete__identite">
            <strong>{profil.first_name} {profil.last_name}</strong>
            <RoleBadge role={profil.role} />
          </div>
          <button className="bouton bouton--discret" onClick={handleDeconnexion}>
            Déconnexion
          </button>
        </div>
      </header>
      <main className="contenu" ref={contenuRef}>
        <Outlet />
      </main>
    </div>
  )
}
