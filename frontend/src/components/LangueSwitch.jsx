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
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M3 12h18M12 3c2.6 2.7 3.9 5.7 3.9 9s-1.3 6.3-3.9 9c-2.6-2.7-3.9-5.7-3.9-9S9.4 5.7 12 3z" />
      </svg>
      {libelle}
    </button>
  )
}
