import { useEffect, useState } from 'react'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

export default function JoursFeriesPage() {
  const [jours, setJours] = useState(null)
  const [date, setDate] = useState('')
  const [libelle, setLibelle] = useState('')
  const [recurrent, setRecurrent] = useState(true)
  const [erreur, setErreur] = useState('')

  function charger() {
    api.get('/jours-feries/').then(({ data }) => setJours(data.results))
  }

  useEffect(charger, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur('')
    try {
      await api.post('/jours-feries/', { date, libelle, recurrent })
      setDate('')
      setLibelle('')
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function supprimer(id) {
    if (!window.confirm('Supprimer ce jour férié ?')) return
    await api.delete(`/jours-feries/${id}/`)
    charger()
  }

  return (
    <div className="page">
      <h1>Jours fériés &amp; fermetures</h1>

      <Carte titre="Ajouter un jour férié / une fermeture">
        <form className="formulaire" onSubmit={handleSubmit}>
          <div className="formulaire__ligne">
            <label>
              Date
              <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label>
              Libellé
              <input type="text" required value={libelle} onChange={(e) => setLibelle(e.target.value)} />
            </label>
          </div>
          <label className="case-a-cocher">
            <input type="checkbox" checked={recurrent} onChange={(e) => setRecurrent(e.target.checked)} />
            Récurrent chaque année
          </label>
          <Alerte type="erreur">{erreur}</Alerte>
          <button className="bouton bouton--primaire" type="submit">Ajouter</button>
        </form>
      </Carte>

      <Carte titre="Jours déclarés">
        {jours === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead><tr><th>Date</th><th>Libellé</th><th>Récurrent</th><th></th></tr></thead>
            <tbody>
              {jours.map((j) => (
                <tr key={j.id}>
                  <td>{j.date}</td>
                  <td>{j.libelle}</td>
                  <td>{j.recurrent ? 'Oui' : 'Non'}</td>
                  <td><button className="bouton bouton--danger" onClick={() => supprimer(j.id)}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
