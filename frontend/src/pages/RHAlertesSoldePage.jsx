import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

const ANNEE_COURANTE = new Date().getFullYear()

export default function RHAlertesSoldePage() {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api.get('/dashboard/rh/alertes-solde/', { params: { annee: ANNEE_COURANTE } })
      .then(({ data }) => setDonnees(data))
      .catch((err) => setErreur(messageErreur(err)))
  }, [])

  if (erreur) return <div className="page"><Alerte type="erreur">{erreur}</Alerte></div>
  if (!donnees) return <Chargement />

  return (
    <div className="page">
      <p><Link to="/rh/dashboard">← Indicateurs RH</Link></p>
      <h1>Alertes de solde faible — {donnees.annee}</h1>
      <p className="texte-discret">
        Soldes dont les jours restants sont inférieurs ou égaux au seuil d’alerte du type de congé : {donnees.count}.
      </p>
      {donnees.count === 0 ? (
        <Carte><p className="texte-discret">Aucun solde sous son seuil d’alerte.</p></Carte>
      ) : (
        <Carte titre="Soldes concernés">
          <table className="tableau tableau--chiffres">
            <thead>
              <tr>
                <th>Employé</th><th>Matricule</th><th>Département</th><th>Type de congé</th>
                <th>Jours acquis</th><th>Jours restants</th><th>Seuil d’alerte</th>
              </tr>
            </thead>
            <tbody>
              {donnees.results.map((a) => (
                <tr key={a.solde}>
                  <td>{a.nom_complet}</td>
                  <td>{a.matricule}</td>
                  <td>{a.departement || '—'}</td>
                  <td>{a.type_conge}</td>
                  <td>{a.jours_acquis}</td>
                  <td><strong>{a.jours_restants}</strong></td>
                  <td>{a.seuil_alerte}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Carte>
      )}
    </div>
  )
}
