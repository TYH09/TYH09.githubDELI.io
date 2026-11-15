import { Link } from 'react-router-dom'
import { useI18n } from '../i18n/I18nContext'

export default function ForbiddenPage() {
  const { t } = useI18n()
  return (
    <div className="page page--erreur">
      <h1>{t('403 — Accès refusé')}</h1>
      <p>{t("Votre rôle ne permet pas d'accéder à cette page.")}</p>
      <Link className="bouton bouton--primaire" to="/">{t('Retour au tableau de bord')}</Link>
    </div>
  )
}
