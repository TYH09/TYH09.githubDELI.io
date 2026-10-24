/**
 * Garde de route : exige une session active, et optionnellement un rôle
 * parmi `roles`. C'est une protection de confort côté frontend — la
 * véritable application du RBAC reste faite par l'API (chaque action est
 * revérifiée côté serveur, cf. conges/permissions.py).
 */
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function RequireAuth({ roles, children }) {
  const { estConnecte, chargementInitial, profil, aDeconnecteVolontairement } = useAuth()
  const location = useLocation()

  if (chargementInitial) return null // évite un flash de redirection pendant le chargement initial

  if (!estConnecte) {
    // Session expirée / accès direct par lien : on mémorise la page demandée pour y
    // revenir après connexion. Après une déconnexion volontaire, on ne mémorise rien.
    const state = aDeconnecteVolontairement() ? undefined : { depuis: location }
    return <Navigate to="/connexion" state={state} replace />
  }
  if (roles && !roles.includes(profil.role)) {
    return <Navigate to="/acces-refuse" replace />
  }
  return children
}
