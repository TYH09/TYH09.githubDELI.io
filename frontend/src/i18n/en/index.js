/**
 * Dictionnaire français → anglais, assemblé à partir d'un fichier par domaine.
 * Clé = texte français exact ; `{valeur}` = emplacement d'une valeur variable.
 */
import communs from './communs.js'
import pagesUtilisateurs from './pages-utilisateurs.js'
import pagesDemandes from './pages-demandes.js'
import pagesRh from './pages-rh.js'
import pagesConfiguration from './pages-configuration.js'
import serveur from './serveur.js'

export default {
  ...communs,
  ...pagesUtilisateurs,
  ...pagesDemandes,
  ...pagesRh,
  ...pagesConfiguration,
  ...serveur,
}
