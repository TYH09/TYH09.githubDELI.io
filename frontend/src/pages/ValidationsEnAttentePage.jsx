import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { listerTout, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import Justificatif from '../components/Justificatif'
import { useI18n } from '../i18n/I18nContext'

/**
 * Page générique de validation à un niveau donné du circuit — réutilisée
 * pour le Manager (1er niveau) et la Direction Générale (2e niveau, décision
 * finale), qui partagent le même patron d'interaction.
 */
function LigneAValider({ demande, actionPath, onTraitee }) {
  const { t } = useI18n()
  const [commentaire, setCommentaire] = useState('')
  const [enCours, setEnCours] = useState('')
  const [erreur, setErreur] = useState('')

  async function decider(decision) {
    setEnCours(decision)
    setErreur('')
    try {
      const { data } = await api.post(`/demandes/${demande.id}/${actionPath}/`, { decision, commentaire })
      onTraitee(data)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours('')
    }
  }

  return (
    <tr>
      <td>
        <Link to={`/demandes/${demande.id}`}>
          <strong>{demande.utilisateur_detail.first_name} {demande.utilisateur_detail.last_name}</strong>
        </Link>
        <br />
        <span className="texte-discret">{demande.utilisateur_detail.departement_nom}</span>
      </td>
      <td>{t(demande.type_conge_libelle)}</td>
      <td>{demande.date_debut} → {demande.date_fin}</td>
      <td>{demande.est_maternite ? t('{n} (maternité, calendaires)', { n: demande.nb_jours_decomptes }) : demande.nb_jours_ouvres}</td>
      <td>{demande.motif || '—'}</td>
      <td><Justificatif demande={demande} /></td>
      <td className="validation__action">
        <input
          type="text"
          placeholder={t('Commentaire (optionnel)')}
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
        />
        <div className="tableau__actions">
          <button className="bouton bouton--succes" disabled={!!enCours} onClick={() => decider('APPROUVE')}>
            {enCours === 'APPROUVE' ? '…' : t('Approuver')}
          </button>
          <button className="bouton bouton--danger" disabled={!!enCours} onClick={() => decider('REFUSE')}>
            {enCours === 'REFUSE' ? '…' : t('Refuser')}
          </button>
        </div>
        <Alerte type="erreur">{erreur}</Alerte>
      </td>
    </tr>
  )
}

export default function ValidationsEnAttentePage({ niveau, actionPath, titre }) {
  const { t } = useI18n()
  const [demandes, setDemandes] = useState(null)

  const charger = useCallback(() => {
    listerTout('/demandes/', { statut: niveau }).then(setDemandes)
  }, [niveau])

  useEffect(() => {
    charger()
  }, [charger])

  function surDemandeTraitee(demandeMaj) {
    setDemandes((prev) => prev.filter((d) => d.id !== demandeMaj.id))
  }

  return (
    <div className="page">
      <h1>{t(titre)}</h1>
      <Carte>
        {demandes === null ? (
          <Chargement />
        ) : demandes.length === 0 ? (
          <p className="texte-discret">{t('Aucune demande en attente de votre décision 🎉')}</p>
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>{t('Employé')}</th><th>{t('Type')}</th><th>{t('Période')}</th><th>{t('Jours ouvrés')}</th><th>{t('Motif')}</th><th>{t('Justificatif')}</th><th>{t('Décision')}</th></tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <LigneAValider key={d.id} demande={d} actionPath={actionPath} onTraitee={surDemandeTraitee} />
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
