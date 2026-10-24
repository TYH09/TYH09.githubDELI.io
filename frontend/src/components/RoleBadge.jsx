const LIBELLES = {
  EMPLOYE: 'Employé',
  MANAGER: 'Manager',
  DIRECTEUR: 'Direction Générale',
  RH: 'Responsable RH',
  ADMINISTRATEUR: 'Administrateur',
}

export default function RoleBadge({ role }) {
  return <span className="badge badge--role">{LIBELLES[role] || role}</span>
}
