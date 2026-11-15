import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

export default function EquipePage() {
  const { t } = useI18n()
  const { profil } = useAuth()
  const [membres, setMembres] = useState(null)

  useEffect(() => {
    api
      .get('/utilisateurs/', { params: { departement: profil.departement } })
      .then(({ data }) => setMembres(data.results))
  }, [profil.departement])

  return (
    <div className="page">
      <h1>{t('Mon équipe')}</h1>
      <Carte titre={profil.departement_nom}>
        {membres === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead><tr><th>{t('Nom')}</th><th>{t('Rôle')}</th><th>{t('E-mail')}</th><th>{t('Téléphone')}</th><th>{t('Actif')}</th></tr></thead>
            <tbody>
              {membres.map((m) => (
                <tr key={m.id}>
                  <td>{m.first_name} {m.last_name}</td>
                  <td>{t(m.role_affiche)}</td>
                  <td>{m.email}</td>
                  <td>{m.telephone || '—'}</td>
                  <td>{m.actif ? t('Oui') : t('Non')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
