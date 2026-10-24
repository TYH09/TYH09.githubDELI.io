/**
 * Client HTTP central (axios) : préfixe /api, injecte le token JWT, et
 * tente un rafraîchissement automatique une fois en cas de 401 avant de
 * déconnecter l'utilisateur.
 */
import axios from 'axios'

const ACCESS_KEY = 'gc_access_token'
const REFRESH_KEY = 'gc_refresh_token'

export const tokenStorage = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = tokenStorage.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let rafraichissementEnCours = null

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const requeteOriginale = error.config
    const estAppelAuth = requeteOriginale?.url?.includes('/auth/token')

    if (error.response?.status === 401 && !requeteOriginale._retry && !estAppelAuth) {
      requeteOriginale._retry = true
      const refresh = tokenStorage.getRefresh()
      if (!refresh) {
        tokenStorage.clear()
        return Promise.reject(error)
      }
      try {
        rafraichissementEnCours =
          rafraichissementEnCours ||
          axios.post('/api/auth/token/refresh/', { refresh }).finally(() => {
            rafraichissementEnCours = null
          })
        const { data } = await rafraichissementEnCours
        tokenStorage.set(data.access, data.refresh || refresh)
        requeteOriginale.headers.Authorization = `Bearer ${data.access}`
        return api(requeteOriginale)
      } catch (erreurRafraichissement) {
        tokenStorage.clear()
        window.location.assign('/connexion')
        return Promise.reject(erreurRafraichissement)
      }
    }
    return Promise.reject(error)
  }
)

/** Récupère TOUTES les pages d'une route paginée (l'API pagine par 20). */
export async function listerTout(url, params = {}) {
  const resultats = []
  for (let page = 1; page < 200; page += 1) {
    const { data } = await api.get(url, { params: { ...params, page } })
    resultats.push(...data.results)
    if (!data.next) break
  }
  return resultats
}

/** Extrait un message d'erreur lisible d'une réponse DRF (detail, non_field_errors, ou premier champ en erreur). */
export function messageErreur(error) {
  const data = error?.response?.data
  if (!data) return error?.message || "Une erreur inconnue s'est produite."
  if (typeof data === 'string') return data
  if (data.detail) return Array.isArray(data.detail) ? data.detail.join(' ') : data.detail
  if (data.non_field_errors) return data.non_field_errors.join(' ')
  const premiereCle = Object.keys(data)[0]
  if (premiereCle) {
    const valeur = data[premiereCle]
    return `${premiereCle} : ${Array.isArray(valeur) ? valeur.join(' ') : valeur}`
  }
  return "Une erreur inconnue s'est produite."
}

export default api
