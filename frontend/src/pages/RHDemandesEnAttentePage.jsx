import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import StatutBadge from '../components/StatutBadge'
import { useI18n } from '../i18n/I18nContext'

// Circuit d'un employé : Manager puis Direction. Circuits à 1 niveau : chef de département et RH
// (validés par un directeur), directeur (validé par le responsable RH).
const ETAPES = [
  { statut: 'EN_ATTENTE_MANAGER', libelle: 'Niveau 1 — Chef de département' },
  { statut: 'EN_ATTENTE_DIRECTION', libelle: 'Niveau 2 — Direction Générale' },
  { statut: 'EN_ATTENTE_RH', libelle: 'Demandes des directeurs — Responsable RH' },
]

function Progression({ demande }) {
  const { t } = useI18n()
  if (demande.utilisateur_detail.role !== 'EMPLOYE') {
    const unNiveau = demande.statut === 'EN_ATTENTE_RH' ? t('Responsable RH') : t('Direction')
    return <span className="texte-discret">{t('Validation à 1 niveau — {valideur}', { valideur: unNiveau })}</span>
  }
  const manager = demande.validations.find((v) => v.niveau === 'MANAGER' && v.decision === 'APPROUVE')
  const enAttenteManager = demande.statut === 'EN_ATTENTE_MANAGER'
  return (
    <ol className="progression" aria-label={t('Niveaux de validation')}>
      <li className={manager ? 'progression__etape progression__etape--ok' : 'progression__etape progression__etape--courante'}>
        {t('1. Manager')}{' '}{manager ? `✔ ${manager.auteur_nom}` : enAttenteManager ? t('— en attente') : ''}
      </li>
      <li className={enAttenteManager ? 'progression__etape' : 'progression__etape progression__etape--courante'}>
        {t('2. Direction')}{' '}{enAttenteManager ? t('— à venir') : t('— en attente')}
      </li>
    </ol>
  )
}

export default function RHDemandesEnAttentePage() {
  const { t } = useI18n()
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
      <p><Link to="/rh/dashboard">{t('← Indicateurs RH')}</Link></p>
      <h1>{t('Demandes en attente')}</h1>
      {ETAPES.map((etape) => {
        const liste = demandes.filter((d) => d.statut === etape.statut)
        return (
          <Carte key={etape.statut} titre={`${t(etape.libelle)} (${liste.length})`}>
            {liste.length === 0 ? (
              <p className="texte-discret">{t('Aucune demande à ce niveau.')}</p>
            ) : (
              <table className="tableau">
                <thead>
                  <tr>
                    <th>{t('Employé')}</th><th>{t('Département')}</th><th>{t('Type')}</th><th>{t('Période')}</th>
                    <th>{t('Niveau de validation')}</th><th>{t('Statut')}</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {liste.map((d) => (
                    <tr key={d.id}>
                      <td>{d.utilisateur_detail.first_name} {d.utilisateur_detail.last_name}</td>
                      <td>{d.utilisateur_detail.departement_nom || '—'}</td>
                      <td>{t(d.type_conge_libelle)}</td>
                      <td>{d.date_debut} → {d.date_fin}</td>
                      <td><Progression demande={d} /></td>
                      <td><StatutBadge statut={d.statut} /></td>
                      <td><Link className="bouton bouton--discret" to={`/demandes/${d.id}`}>{t('Voir la demande')}</Link></td>
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
