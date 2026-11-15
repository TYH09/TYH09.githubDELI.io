import { useState } from 'react'
import { useI18n } from '../i18n/I18nContext'

/**
 * Champ mot de passe avec bouton « œil » : permet de voir (ou masquer) ce que
 * l'on est en train de saisir. Même props qu'un <input>.
 */
export default function ChampMotDePasse({ autoComplete = 'current-password', ...props }) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)
  return (
    <span className="champ-mdp">
      <input {...props} type={visible ? 'text' : 'password'} autoComplete={autoComplete} />
      <button
        type="button"
        className="champ-mdp__bascule"
        onClick={() => setVisible((v) => !v)}
        aria-pressed={visible}
        aria-label={visible ? t('Masquer le mot de passe') : t('Afficher le mot de passe')}
        title={visible ? t('Masquer le mot de passe') : t('Afficher le mot de passe')}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
        <circle cx="12" cy="12" r="3" />
        {visible && <path d="M3 3l18 18" />}
      </svg>
      </button>
    </span>
  )
}
