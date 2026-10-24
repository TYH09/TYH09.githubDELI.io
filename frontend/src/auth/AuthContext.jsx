/**
 * Contexte d'authentification : connexion/déconnexion, profil courant
 * (avec rôle — RBAC) et soldes de congés de l'année en cours.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import api, { messageErreur, tokenStorage } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [profil, setProfil] = useState(null)
  const [soldes, setSoldes] = useState([])
  // Chargement initial seulement si un token existe déjà (restauration de session)
  const [chargementInitial, setChargementInitial] = useState(() => !!tokenStorage.getAccess())
  const [erreurConnexion, setErreurConnexion] = useState('')
  // Vrai après un clic sur « Déconnexion » : évite que la garde de route
  // mémorise la page quittée comme destination de retour pour le compte
  // suivant (qui pourrait ne pas avoir le droit d'y accéder).
  const deconnexionVolontaire = useRef(false)

  const chargerMoi = useCallback(async () => {
    const { data } = await api.get('/me/')
    setProfil(data.profil)
    setSoldes(data.soldes)
    return data.profil
  }, [])

  useEffect(() => {
    if (!tokenStorage.getAccess()) return
    chargerMoi()
      .catch(() => tokenStorage.clear()) // token invalide/expiré : on repart d'une session vierge
      .finally(() => setChargementInitial(false))
  }, [chargerMoi])

  const connecter = useCallback(
    async (username, password) => {
      setErreurConnexion('')
      try {
        const { data } = await api.post('/auth/token/', { username, password })
        tokenStorage.set(data.access, data.refresh)
        deconnexionVolontaire.current = false
        await chargerMoi()
        return true
      } catch (err) {
        setErreurConnexion(
          err.response?.status === 401 ? 'Identifiants incorrects.' : messageErreur(err)
        )
        return false
      }
    },
    [chargerMoi]
  )

  const deconnecter = useCallback(() => {
    deconnexionVolontaire.current = true
    tokenStorage.clear()
    setProfil(null)
    setSoldes([])
  }, [])

  const valeur = useMemo(
    () => ({
      profil,
      soldes,
      estConnecte: !!profil,
      chargementInitial,
      erreurConnexion,
      connecter,
      deconnecter,
      rafraichirProfil: chargerMoi,
      aDeconnecteVolontairement: () => deconnexionVolontaire.current,
    }),
    [profil, soldes, chargementInitial, erreurConnexion, connecter, deconnecter, chargerMoi]
  )

  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé à l’intérieur de <AuthProvider>.')
  return ctx
}
