import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import StatutBadge from '../components/StatutBadge'

// Les deux niveaux du circuit : Manager (chef de département) puis Direction.
const ETAPES = [
  { statut: 'EN_ATTENTE_MANAGER', libelle: 'Niveau 1 — Chef de département' },
  { statut: 'EN_ATTENTE_DIRECTION', libelle: 'Niveau 2 — Direction Générale' },
]

function Progression({ demande }) {
  const manager = demande.validations.find((v) => v.niveau === 'MANAGER' && v.decision === 'APPROUVE')
  const enAttenteManager = demande.statut === 'EN_ATTENTE_MANAGER'
  return (
    <ol className="progression" aria-label="Niveaux de validation">
      <li className={manager ? 'progression__etape progression__etape--ok' : 'progression__etape progression__etape--courante'}>
        1. Manager {manager ? `✔ ${manager.auteur_nom}` : enAttenteManager ? '— en attente' : ''}
      </li>
      <li className={enAttenteManager ? 'progression__etape' : 'progression__etape progression__etape--courante'}>
        2. Direction {enAttenteManager ? '— à venir' : '— en attente'}
      </li>
    </ol>
  )
}

export default function RHDemandesEnAttentePage() {
  const [demandes, setDemandes] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api.get('/dashboard/rh/demandes-en-attente/')
      .then(({ data }) => setDemandes(data.results))
      .catch((err) => setErreur(messageErreur(err)))
  }, [])

  if (erreur) return <div className="page"><Alerte type="erreur">{erreur}</Alerte></div>
  if (!demandes) return <Chargement />

  return (
    <div className="page">
      <p><Link to="/rh/dashboard">← Indicateurs RH</Link></p>
      <h1>Demandes en attente</h1>
      {ETAPES.map((etape) => {
        const liste = demandes.filter((d) => d.statut === etape.statut)
        return (
          <Carte key={etape.statut} titre={`${etape.libelle} (${liste.length})`}>
            {liste.length === 0 ? (
              <p className="texte-discret">Aucune demande à ce niveau.</p>
            ) : (
              <table className="tableau">
                <thead>
                  <tr>
                    <th>Employé</th><th>Département</th><th>Type</th><th>Période</th>
                    <th>Niveau de validation</th><th>Statut</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {liste.map((d) => (
                    <tr key={d.id}>
                      <td>{d.utilisateur_detail.first_name} {d.utilisateur_detail.last_name}</td>
                      <td>{d.utilisateur_detail.departement_nom || '—'}</td>
                      <td>{d.type_conge_libelle}</td>
                      <td>{d.date_debut} → {d.date_fin}</td>
                      <td><Progression demande={d} /></td>
                      <td><StatutBadge statut={d.statut} /></td>
                      <td><Link className="bouton bouton--discret" to={`/demandes/${d.id}`}>Voir la demande</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Carte>
        )
      })}
    </div>
  )
}
