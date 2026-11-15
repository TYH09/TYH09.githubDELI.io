import { useI18n } from '../i18n/I18nContext'

// Les messages (y compris ceux renvoyés par le serveur) sont traduits s'ils figurent au dictionnaire.
export default function Alerte({ type = 'info', children }) {
  const { t } = useI18n()
  if (!children) return null
  return <div className={`alerte alerte--${type}`}>{typeof children === 'string' ? t(children) : children}</div>
}
