import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

const ANNEE_COURANTE = new Date().getFullYear()

export default function RHAlertesSoldePage() {
  const { t } = useI18n()
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
      <p><Link to="/rh/dashboard">{t('← Indicateurs RH')}</Link></p>
      <h1>{t('Alertes de solde faible — {annee}', { annee: donnees.annee })}</h1>
      <p className="texte-discret">
        {t('Soldes dont les jours restants sont inférieurs ou égaux au seuil d’alerte du type de congé : {n}.', { n: donnees.count })}
      </p>
      {donnees.count === 0 ? (
        <Carte><p className="texte-discret">{t('Aucun solde sous son seuil d’alerte.')}</p></Carte>
      ) : (
        <Carte titre={t('Soldes concernés')}>
          <table className="tableau tableau--chiffres">
            <thead>
              <tr>
                <th>{t('Employé')}</th><th>{t('Matricule')}</th><th>{t('Département')}</th><th>{t('Type de congé')}</th>
                <th>{t('Jours acquis')}</th><th>{t('Jours restants')}</th><th>{t('Seuil d’alerte')}</th>
              </tr>
            </thead>
            <tbody>
              {donnees.results.map((a) => (
                <tr key={a.solde}>
                  <td>{a.nom_complet}</td>
                  <td>{a.matricule}</td>
                  <td>{a.departement || '—'}</td>
                  <td>{t(a.type_conge)}</td>
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
