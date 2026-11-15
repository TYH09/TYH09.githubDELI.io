import { useI18n } from '../i18n/I18nContext'

const LIBELLES = {
  EMPLOYE: 'Employé',
  MANAGER: 'Manager',
  DIRECTEUR: 'Direction Générale',
  RH: 'Responsable RH',
  ADMINISTRATEUR: 'Administrateur',
}

export default function RoleBadge({ role }) {
  const { t } = useI18n()
  return <span className="badge badge--role">{LIBELLES[role] ? t(LIBELLES[role]) : role}</span>
}
