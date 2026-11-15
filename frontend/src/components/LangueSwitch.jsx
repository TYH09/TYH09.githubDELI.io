import { useI18n } from '../i18n/I18nContext'

/**
 * Bouton de bascule de langue : en français il propose « English », en anglais « Français ».
 * `variante` : « entete » (sur le bandeau rouge) ou « clair » (sur fond clair, page de connexion).
 */
export default function LangueSwitch({ variante = 'entete' }) {
  const { lang, basculer } = useI18n()
  const cible = lang === 'fr' ? 'en' : 'fr'
  // Libellés écrits dans la langue CIBLE (convention des sélecteurs de langue), donc volontairement hors dictionnaire.
  const libelle = cible === 'en' ? 'English' : 'Français'
  const titre = cible === 'en' ? 'Switch to English' : 'Passer en français'
  return (
    <button
      type="button"
      className={`bouton bouton--langue bouton--langue-${variante}`}
      onClick={basculer}
      lang={cible}
      title={titre}
      aria-label={titre}
    >
      <span aria-hidden="true">🌐</span> {libelle}
    </button>
  )
}
