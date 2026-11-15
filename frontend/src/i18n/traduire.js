/**
 * Traduction FR ⇄ EN, sans dépendance.
 *
 * Principe : le texte FRANÇAIS sert de clé. `traduire('Mes demandes')` rend
 * « Mes demandes » en français et « My requests » en anglais ; une clé absente du
 * dictionnaire retombe sur le français (l'interface ne casse jamais).
 *
 * - Valeurs variables : `traduire('Bonjour {nom}', { nom: 'Yves' })`.
 * - Messages venus du serveur (déjà interpolés, ex. « Solde insuffisant : 3 jour(s) ») :
 *   si le texte n'est pas une clé exacte, on le compare aux clés à `{valeur}` du
 *   dictionnaire (« Solde insuffisant : {jours} jour(s) ») et on réinjecte les valeurs.
 *
 * Ce module ne dépend pas de React : il sert aussi hors composants (client API).
 * Dans un composant, utiliser `useI18n()` (I18nContext.jsx), qui re-rend à chaque changement.
 */
import en from './en'

export const LANGUES = ['fr', 'en']
const CLE_STOCKAGE = 'gc_langue'
const DICTIONNAIRES = { en }

function lireLangueEnregistree() {
  try {
    const valeur = localStorage.getItem(CLE_STOCKAGE)
    return LANGUES.includes(valeur) ? valeur : 'fr'
  } catch {
    return 'fr' // stockage indisponible (navigation privée, etc.)
  }
}

let langueCourante = lireLangueEnregistree()

export const getLangue = () => langueCourante

/** Change la langue (mémorisée dans le navigateur) — appelé par le fournisseur React. */
export function definirLangue(langue) {
  if (!LANGUES.includes(langue)) return
  langueCourante = langue
  try {
    localStorage.setItem(CLE_STOCKAGE, langue)
  } catch {
    /* sans importance : le choix vaut pour la session */
  }
  if (typeof document !== 'undefined') document.documentElement.lang = langue
}

/** En développement : clés sans traduction rencontrées (lisible depuis la console ou un test). */
export const clesManquantes = new Set()
if (import.meta.env.DEV && typeof window !== 'undefined') window.__clesManquantes = clesManquantes

/**
 * Injecte les valeurs. Dans une TRADUCTION, `{n:|s}` ou `{n:day|days}` choisit le singulier
 * (valeur = 1) ou le pluriel : « {n} day{n:|s} » → « 1 day », « 3 days ».
 */
const interpoler = (texte, params) =>
  params
    ? texte
        .replace(/\{(\w+):([^|{}]*)\|([^{}]*)\}/g, (brut, nom, singulier, pluriel) =>
          nom in params ? (Number(params[nom]) === 1 ? singulier : pluriel) : brut,
        )
        .replace(/\{(\w+)\}/g, (brut, nom) => (nom in params ? String(params[nom]) : brut))
    : texte

const echapper = (texte) => texte.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const motifsParLangue = {}
const cacheMotifs = new Map()

/** Clés contenant `{valeur}` transformées en expressions régulières (les plus précises d'abord). */
function motifs(langue) {
  if (!motifsParLangue[langue]) {
    motifsParLangue[langue] = Object.entries(DICTIONNAIRES[langue] || {})
      .filter(([cle]) => /\{\w+\}/.test(cle))
      .map(([cle, cible]) => {
        const noms = []
        const source = cle
          .split(/(\{\w+\})/)
          .map((morceau) => {
            const m = morceau.match(/^\{(\w+)\}$/)
            if (m) {
              noms.push(m[1])
              return '([\\s\\S]+?)'
            }
            return echapper(morceau)
          })
          .join('')
        return { regex: new RegExp(`^${source}$`), noms, cible, precision: cle.replace(/\{\w+\}/g, '').length }
      })
      .sort((a, b) => b.precision - a.precision)
  }
  return motifsParLangue[langue]
}

function chercherParMotif(texte, langue) {
  const idCache = `${langue}|${texte}`
  if (cacheMotifs.has(idCache)) return cacheMotifs.get(idCache)
  let resultat = null
  for (const { regex, noms, cible } of motifs(langue)) {
    const trouve = texte.match(regex)
    if (trouve) {
      resultat = interpoler(cible, Object.fromEntries(noms.map((nom, i) => [nom, trouve[i + 1]])))
      break
    }
  }
  cacheMotifs.set(idCache, resultat)
  return resultat
}

/**
 * @param {string} cle     texte français (éventuellement avec `{valeurs}`)
 * @param {object} [params] valeurs à injecter
 * @param {string} [langue] par défaut, la langue courante
 */
export function traduire(cle, params, langue = langueCourante) {
  if (typeof cle !== 'string' || cle === '' || langue === 'fr') return typeof cle === 'string' ? interpoler(cle, params) : cle
  const cible = DICTIONNAIRES[langue]?.[cle]
  if (cible !== undefined) return interpoler(cible, params)
  const parMotif = chercherParMotif(cle, langue)
  if (parMotif !== null) return parMotif
  if (import.meta.env.DEV) clesManquantes.add(cle)
  return interpoler(cle, params)
}
