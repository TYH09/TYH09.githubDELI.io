import { useI18n } from '../i18n/I18nContext'

const STYLES = {
  BROUILLON: { bg: '#f1f4ef', fg: '#4b5648', texte: 'Brouillon' },
  EN_ATTENTE_MANAGER: { bg: '#ffffff', fg: '#c8180e', bordure: '#e0200f', texte: 'En attente — Manager' },
  EN_ATTENTE_DIRECTION: { bg: '#ffffff', fg: '#c8180e', bordure: '#e0200f', texte: 'En attente — Direction' },
  EN_ATTENTE_RH: { bg: '#ffffff', fg: '#c8180e', bordure: '#e0200f', texte: 'En attente — Responsable RH' },
  VALIDEE: { bg: '#eaf8e6', fg: '#14520a', texte: 'Validée' },
  REFUSEE: { bg: '#c8180e', fg: '#ffffff', texte: 'Refusée' },
  ANNULEE: { bg: '#f1f4ef', fg: '#4b5648', texte: 'Annulée' },
}

export default function StatutBadge({ statut }) {
  const { t } = useI18n()
  const style = STYLES[statut] || STYLES.BROUILLON
  return (
    <span className="badge" style={{ backgroundColor: style.bg, color: style.fg, border: `1px solid ${style.bordure || style.bg}` }}>
      {t(style.texte)}
    </span>
  )
}
