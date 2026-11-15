import { Link } from 'react-router-dom'
import { useI18n } from '../i18n/I18nContext'

export default function NotFoundPage() {
  const { t } = useI18n()
  return (
    <div className="page page--erreur">
      <h1>{t('404 — Page introuvable')}</h1>
      <Link className="bouton bouton--primaire" to="/">{t('Retour au tableau de bord')}</Link>
    </div>
  )
}
