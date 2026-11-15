import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { definirLangue, getLangue, traduire } from './traduire'

const LOCALES = { fr: 'fr-FR', en: 'en-GB' }

const I18nContext = createContext(null)

/**
 * Fournit la langue de l'interface (« fr » par défaut, ou le dernier choix de l'utilisateur).
 * Un changement de langue re-rend tous les composants qui appellent `useI18n()`.
 */
export function I18nProvider({ children }) {
  const [lang, setLang] = useState(getLangue)

  const changer = useCallback((nouvelle) => {
    definirLangue(nouvelle)
    setLang(nouvelle)
  }, [])

  const basculer = useCallback(() => changer(lang === 'fr' ? 'en' : 'fr'), [lang, changer])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const valeur = useMemo(
    () => ({
      lang,
      locale: LOCALES[lang], // pour toLocaleString / Intl
      changer,
      basculer,
      t: (cle, params) => traduire(cle, params, lang),
    }),
    [lang, changer, basculer],
  )

  return <I18nContext.Provider value={valeur}>{children}</I18nContext.Provider>
}

/** `const { t, lang, locale } = useI18n()` — `t('Texte français', { valeur })`. */
export function useI18n() {
  const contexte = useContext(I18nContext)
  if (!contexte) throw new Error('useI18n doit être utilisé à l’intérieur de <I18nProvider>.')
  return contexte
}
