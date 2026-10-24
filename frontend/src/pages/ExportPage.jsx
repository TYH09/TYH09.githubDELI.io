import { useState } from 'react'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'

const ANNEE_COURANTE = new Date().getFullYear()
const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

export default function ExportPage() {
  const [annee, setAnnee] = useState(ANNEE_COURANTE)
  const [mois, setMois] = useState('') // '' = tous les mois
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  async function telecharger() {
    setEnCours(true)
    setErreur('')
    try {
      // Le endpoint exige le JWT (en-tête Authorization), donc un simple lien
      // <a href> ne fonctionnerait pas : on récupère le fichier en blob puis
      // on déclenche le téléchargement nous-mêmes.
      const reponse = await api.get('/export/demandes.csv', { params: { annee: annee || undefined, mois: mois || undefined }, responseType: 'blob' })
      const url = window.URL.createObjectURL(reponse.data)
      const lien = document.createElement('a')
      lien.href = url
      const suffixe = [annee || 'toutes_annees', mois ? String(mois).padStart(2, '0') : null].filter(Boolean).join('_')
      lien.download = `conges_valides_${suffixe}.csv`
      document.body.appendChild(lien)
      lien.click()
      lien.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="page">
      <h1>Export des congés validés</h1>
      <Carte titre="Export CSV (Comptabilité)">
        <p className="texte-discret">
          Le fichier ne contient que les demandes <strong>validées</strong> (décision finale de la Direction) :
          employé, matricule, département, type de congé, période, jours ouvrés et date de validation.
          Les demandes en attente, refusées ou annulées n’y figurent pas.
        </p>
        <p className="texte-discret">
          Le tri se fait sur la <strong>date de début</strong> du congé. Laissez l’année vide pour toutes les années.
        </p>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <label>
            Année
            <input
              type="number"
              value={annee}
              placeholder="Toutes"
              onChange={(e) => setAnnee(e.target.value)}
              style={{ maxWidth: 120 }}
            />
          </label>
          <label>
            Mois
            <select value={mois} onChange={(e) => setMois(e.target.value)}>
              <option value="">Tous les mois</option>
              {MOIS.map((nom, i) => (
                <option key={nom} value={i + 1}>{nom}</option>
              ))}
            </select>
          </label>
        </div>
        <Alerte type="erreur">{erreur}</Alerte>
        <div className="tableau__actions">
          <button className="bouton bouton--primaire" onClick={telecharger} disabled={enCours}>
            {enCours ? 'Génération…' : 'Télécharger le CSV'}
          </button>
        </div>
      </Carte>
    </div>
  )
}
