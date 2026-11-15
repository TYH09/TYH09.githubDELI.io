import { useI18n } from '../i18n/I18nContext'

export default function Chargement({ libelle = 'Chargement…' }) {
  const { t } = useI18n()
  return <p className="chargement">{t(libelle)}</p>
}
