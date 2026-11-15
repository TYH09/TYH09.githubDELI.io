import { useEffect, useState } from 'react'
import api, { messageErreur } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

const PERIODES = [
  ['', 'En congé ou à venir'],
  ['en_cours', 'En congé aujourd’hui'],
  ['a_venir', 'Départs à venir'],
]

/** « 2026-10-19 » -> « 19/10/2026 » (sans passer par un fuseau horaire). */
function formaterDate(iso) {
  const [annee, mois, jour] = iso.split('-')
  return `${jour}/${mois}/${annee}`
}

/**
 * Absences de l'équipe : les employés du département du Manager dont un
 * congé a été validé (en cours ou à venir), avec leurs coordonnées et leurs
 * dates de départ et de retour. Le type de congé et le motif ne sont pas
 * affichés : l'API ne les transmet pas (vie privée).
 */
export default function AbsencesEquipePage() {
  const { t } = useI18n()
  const { profil } = useAuth()
  const [periode, setPeriode] = useState('')
  const [absences, setAbsences] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let actif = true
    api
      .get('/equipe/absences/', { params: periode ? { periode } : {} })
      .then(({ data }) => {
        if (!actif) return
        setErreur('')
        setAbsences(data.results)
      })
      .catch((err) => {
        if (actif) setErreur(messageErreur(err))
      })
    return () => {
      actif = false
    }
  }, [periode])

  return (
    <div className="page">
      <div className="page__entete">
        <h1>{t('Absences de l’équipe')}</h1>
        <label className="filtre">
          {t('Afficher')}
          <select value={periode} onChange={(e) => { setAbsences(null); setPeriode(e.target.value) }}>
            {PERIODES.map(([valeur, libelle]) => <option key={valeur} value={valeur}>{t(libelle)}</option>)}
          </select>
        </label>
      </div>

      <Alerte type="erreur">{erreur}</Alerte>

      <Carte titre={profil.departement_nom || t('Mon département')}>
        {absences === null && !erreur ? (
          <Chargement />
        ) : absences && absences.length === 0 ? (
          <p className="texte-discret">{t('Aucun collaborateur en congé sur cette période.')}</p>
        ) : (
          absences && (
            <table className="tableau">
              <thead>
                <tr>
                  <th>{t('Nom')}</th><th>{t('Rôle')}</th><th>{t('E-mail')}</th><th>{t('Téléphone')}</th>
                  <th>{t('Départ')}</th><th>{t('Retour')}</th><th>{t('Situation')}</th>
                </tr>
              </thead>
              <tbody>
                {absences.map((a) => (
                  <tr key={a.demande}>
                    <td><strong>{a.nom_complet}</strong></td>
                    <td>{t(a.role_affiche)}</td>
                    <td>{a.email ? <a href={`mailto:${a.email}`}>{a.email}</a> : '—'}</td>
                    <td>{a.telephone ? <a href={`tel:${a.telephone.replace(/[^+\d]/g, '')}`}>{a.telephone}</a> : '—'}</td>
                    <td>{formaterDate(a.date_depart)}</td>
                    <td>
                      {formaterDate(a.date_retour)}
                      <br />
                      <span className="texte-discret">{t('dernier jour d’absence : {date}', { date: formaterDate(a.date_fin) })}</span>
                    </td>
                    <td>
                      <span className={`badge ${a.statut === 'EN_COURS' ? 'badge--en-conge' : 'badge--a-venir'}`}>
                        {a.statut === 'EN_COURS' ? t('En congé') : t('À venir')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </Carte>
    </div>
  )
}
