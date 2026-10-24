import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

export default function ParametresPage() {
  const [params, setParams] = useState(null)
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')

  useEffect(() => {
    api.get('/parametres-systeme/').then(({ data }) => setParams(data))
  }, [])

  async function enregistrer(e) {
    e.preventDefault()
    setErreur('')
    setSucces('')
    try {
      const { data } = await api.put('/parametres-systeme/', params)
      setParams(data)
      setSucces('Paramètres enregistrés.')
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  if (!params) return <Chargement />

  return (
    <div className="page">
      <h1>Paramètres système</h1>
      <Carte titre="Seuils configurables">
        <p className="texte-discret">
          Valeurs par défaut, appliquées aux types de congés qui n’ont pas leurs propres seuils (voir{' '}
          <Link to="/admin/types-conge">Délais et seuils par type</Link>).
        </p>
        <form className="formulaire" onSubmit={enregistrer}>
          <label>
            Délai minimum de soumission (jours avant la date de début)
            <input
              type="number" min="0" value={params.delai_minimum_jours}
              onChange={(e) => setParams({ ...params, delai_minimum_jours: Number(e.target.value) })}
            />
          </label>
          <label>
            Seuil d'alerte solde faible (jours restants)
            <input
              type="number" min="0" value={params.seuil_alerte_solde_jours}
              onChange={(e) => setParams({ ...params, seuil_alerte_solde_jours: Number(e.target.value) })}
            />
          </label>
          <Alerte type="erreur">{erreur}</Alerte>
          <Alerte type="succes">{succes}</Alerte>
          <button className="bouton bouton--primaire" type="submit">Enregistrer</button>
        </form>
      </Carte>
    </div>
  )
}
