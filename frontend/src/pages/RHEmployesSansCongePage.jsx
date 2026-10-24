import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

const ANNEE_COURANTE = new Date().getFullYear()

export default function RHEmployesSansCongePage() {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api.get('/dashboard/rh/employes-sans-conge-annuel/', { params: { annee: ANNEE_COURANTE } })
      .then(({ data }) => setDonnees(data))
      .catch((err) => setErreur(messageErreur(err)))
  }, [])

  if (erreur) return <div className="page"><Alerte type="erreur">{erreur}</Alerte></div>
  if (!donnees) return <Chargement />

  // Regroupement par département pour une lecture rapide.
  const parDepartement = donnees.results.reduce((acc, e) => {
    const cle = e.departement || 'Sans département'
    ;(acc[cle] = acc[cle] || []).push(e)
    return acc
  }, {})

  return (
    <div className="page">
      <p><Link to="/rh/dashboard">← Indicateurs RH</Link></p>
      <h1>Employés éligibles sans congé annuel validé — {donnees.annee}</h1>
      <p className="texte-discret">
        Employés ayant au moins un an d’ancienneté et aucun congé annuel validé cette année : {donnees.count}.
      </p>
      {donnees.count === 0 ? (
        <Carte><p className="texte-discret">Tous les employés éligibles ont déjà pris un congé annuel.</p></Carte>
      ) : (
        <Carte titre="Liste des employés">
          <table className="tableau">
            <thead>
              <tr>
                <th>Employé</th><th>Matricule</th><th>Département</th><th>Ancienneté</th>
                <th>Droit annuel</th><th>Jours restants</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(parDepartement).map(([dep, liste]) => liste.map((e) => (
                <tr key={e.utilisateur}>
                  <td>{e.nom_complet}</td>
                  <td>{e.matricule}</td>
                  <td>{dep}</td>
                  <td>{e.anciennete_annees} an{e.anciennete_annees > 1 ? 's' : ''}</td>
                  <td>{e.droit_conge_annuel} j</td>
                  <td>{e.jours_restants ?? '—'}</td>
                </tr>
              )))}
            </tbody>
          </table>
        </Carte>
      )}
    </div>
  )
}
