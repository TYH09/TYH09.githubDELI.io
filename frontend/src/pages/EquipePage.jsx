import { useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'

export default function EquipePage() {
  const { profil } = useAuth()
  const [membres, setMembres] = useState(null)

  useEffect(() => {
    api
      .get('/utilisateurs/', { params: { departement: profil.departement } })
      .then(({ data }) => setMembres(data.results))
  }, [profil.departement])

  return (
    <div className="page">
      <h1>Mon équipe</h1>
      <Carte titre={profil.departement_nom}>
        {membres === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead><tr><th>Nom</th><th>Rôle</th><th>E-mail</th><th>Téléphone</th><th>Actif</th></tr></thead>
            <tbody>
              {membres.map((m) => (
                <tr key={m.id}>
                  <td>{m.first_name} {m.last_name}</td>
                  <td>{m.role_affiche}</td>
                  <td>{m.email}</td>
                  <td>{m.telephone || '—'}</td>
                  <td>{m.actif ? 'Oui' : 'Non'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
