import { useEffect, useState } from 'react'
import api, { listerTout, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

export default function DepartementsPage() {
  const [departements, setDepartements] = useState(null)
  const [managers, setManagers] = useState([])
  const [directeurs, setDirecteurs] = useState([])
  const [nom, setNom] = useState('')
  const [erreur, setErreur] = useState('')

  function charger() {
    listerTout('/departements/').then(setDepartements)
  }

  useEffect(() => {
    charger()
    listerTout('/utilisateurs/', { role: 'MANAGER', actif: true }).then(setManagers)
    listerTout('/utilisateurs/', { role: 'DIRECTEUR', actif: true }).then(setDirecteurs)
  }, [])

  async function creer(e) {
    e.preventDefault()
    setErreur('')
    try {
      await api.post('/departements/', { nom })
      setNom('')
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function modifier(id, champs) {
    setErreur('')
    try {
      await api.patch(`/departements/${id}/`, champs)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function supprimer(d) {
    if (!window.confirm(`Supprimer le département « ${d.nom} » ? Cette action est irréversible.`)) return
    setErreur('')
    try {
      await api.delete(`/departements/${d.id}/`)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>Départements</h1>
      <Alerte type="erreur">{erreur}</Alerte>

      <Carte titre="Créer un département">
        <form className="formulaire formulaire--ligne" onSubmit={creer}>
          <label>
            Nom
            <input value={nom} onChange={(e) => setNom(e.target.value)} required />
          </label>
          <button className="bouton bouton--primaire" type="submit">Créer</button>
        </form>
      </Carte>

      <Carte titre="Départements existants">
        {departements === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>Nom</th><th>Chef de département (1er niveau)</th><th>Directeur superviseur (2e niveau)</th><th></th></tr>
            </thead>
            <tbody>
              {departements.map((d) => (
                <tr key={d.id}>
                  <td>{d.nom}</td>
                  <td>
                    <select value={d.responsable || ''} onChange={(e) => modifier(d.id, { responsable: e.target.value || null })}>
                      <option value="">— Aucun —</option>
                      {managers.map((m) => (
                        <option key={m.id} value={m.id}>{m.first_name} {m.last_name}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      aria-label={`Directeur de ${d.nom}`}
                      value={d.directeur || ''}
                      onChange={(e) => modifier(d.id, { directeur: e.target.value || null })}
                    >
                      <option value="">— Toute la Direction —</option>
                      {directeurs.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.first_name} {m.last_name}{m.fonction_direction ? ` (${m.fonction_direction})` : ''}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button className="bouton bouton--danger" onClick={() => supprimer(d)}>Supprimer</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
