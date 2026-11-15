import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { messageErreur } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import StatutBadge from '../components/StatutBadge'
import Justificatif from '../components/Justificatif'
import { versFr } from '../utils/dates'
import { useI18n } from '../i18n/I18nContext'

const STATUTS_ANNULABLES = ['BROUILLON', 'EN_ATTENTE_MANAGER', 'EN_ATTENTE_DIRECTION']

/** Formulaire de décision : visible seulement pour celui dont c'est le tour. */
function FormulaireDecision({ demande, actionPath, onDecidee }) {
  const { t } = useI18n()
  const [commentaire, setCommentaire] = useState('')
  const [enCours, setEnCours] = useState('')
  const [erreur, setErreur] = useState('')

  async function decider(decision) {
    setEnCours(decision)
    setErreur('')
    try {
      const { data } = await api.post(`/demandes/${demande.id}/${actionPath}/`, { decision, commentaire })
      onDecidee(data, decision)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours('')
    }
  }

  return (
    <Carte titre={t('Votre décision')}>
      <div className="formulaire">
        <label>
          {t('Commentaire (optionnel)')}
          <input type="text" value={commentaire} maxLength={255} onChange={(e) => setCommentaire(e.target.value)} />
        </label>
        <Alerte type="erreur">{erreur}</Alerte>
        <div className="tableau__actions">
          <button className="bouton bouton--succes" disabled={!!enCours} onClick={() => decider('APPROUVE')}>
            {enCours === 'APPROUVE' ? '…' : t('Approuver')}
          </button>
          <button className="bouton bouton--danger" disabled={!!enCours} onClick={() => decider('REFUSE')}>
            {enCours === 'REFUSE' ? '…' : t('Refuser')}
          </button>
        </div>
      </div>
    </Carte>
  )
}

/**
 * Détail d'une demande de congé. C'est la destination des notifications :
 * le Manager et le Directeur y arrivent en cliquant sur la notification et
 * peuvent décider directement. L'API ne renvoie la demande qu'aux personnes
 * de son périmètre (sinon 404, affiché comme « introuvable »).
 */
export default function DemandeDetailPage() {
  const { t } = useI18n()
  const { id } = useParams()
  const navigate = useNavigate()
  const { profil, rafraichirProfil } = useAuth()
  const [demande, setDemande] = useState(null)
  const [erreur, setErreur] = useState('')
  const [introuvable, setIntrouvable] = useState(false)
  const [message, setMessage] = useState('')
  const [erreurAction, setErreurAction] = useState('')

  useEffect(() => {
    let actif = true
    api
      .get(`/demandes/${id}/`)
      .then(({ data }) => {
        if (!actif) return
        setDemande(data)
        setIntrouvable(false)
      })
      .catch((err) => {
        if (!actif) return
        if (err?.response?.status === 404) setIntrouvable(true)
        else setErreur(messageErreur(err))
      })
    return () => {
      actif = false
    }
  }, [id])

  if (introuvable) {
    return (
      <div className="page">
        <h1>{t('Demande introuvable')}</h1>
        <Alerte type="info">
          {t('Cette demande n’existe pas ou n’entre pas dans votre périmètre.')}
        </Alerte>
        <button className="bouton bouton--discret" onClick={() => navigate(-1)}>{t('← Retour')}</button>
      </div>
    )
  }
  if (erreur) return <div className="page"><Alerte type="erreur">{erreur}</Alerte></div>
  if (!demande) return <Chargement />

  const u = demande.utilisateur_detail
  const actionPath =
    profil.role === 'MANAGER' && demande.statut === 'EN_ATTENTE_MANAGER' ? 'valider-manager'
      : profil.role === 'DIRECTEUR' && demande.statut === 'EN_ATTENTE_DIRECTION' && demande.utilisateur !== profil.id ? 'valider-direction'
        : profil.role === 'RH' && demande.statut === 'EN_ATTENTE_RH' ? 'valider-rh'
          : null
  const peutAnnuler =
    demande.utilisateur === profil.id && STATUTS_ANNULABLES.includes(demande.statut)

  function surDecision(maj, decision) {
    setDemande(maj)
    setMessage(decision === 'APPROUVE' ? t('Demande approuvée.') : t('Demande refusée.'))
  }

  async function annuler() {
    if (!window.confirm(t('Confirmer l’annulation de cette demande ?'))) return
    setErreurAction('')
    try {
      const { data } = await api.post(`/demandes/${demande.id}/annuler/`)
      setDemande(data)
      setMessage(t('Demande annulée.'))
      rafraichirProfil()
    } catch (err) {
      setErreurAction(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <div className="page__entete">
        <h1>{t('Demande de congé n° {id}', { id: demande.id })}</h1>
        <button className="bouton bouton--discret" onClick={() => navigate(-1)}>{t('← Retour')}</button>
      </div>

      <Alerte type="succes">{message}</Alerte>

      <div className="grille-cartes">
        <Carte titre={t('Demandeur')}>
          <p><strong>{u.first_name} {u.last_name}</strong></p>
          <p className="texte-discret">{t(u.role_affiche)}{u.departement_nom && ` · ${u.departement_nom}`}</p>
          <p className="texte-discret">
            {u.email ? <a href={`mailto:${u.email}`}>{u.email}</a> : t('e-mail non renseigné')}
            {' · '}
            {u.telephone ? <a href={`tel:${u.telephone.replace(/[^+\d]/g, '')}`}>{u.telephone}</a> : t('téléphone non renseigné')}
          </p>
        </Carte>

        <Carte titre={t('Demande')}>
          <p><strong>{t(demande.type_conge_libelle)}</strong> <StatutBadge statut={demande.statut} /></p>
          <p>
            {demande.date_debut} → {demande.date_fin} ·{' '}
            {demande.est_maternite
              ? t('{n} jours calendaires décomptés', { n: demande.nb_jours_decomptes })
              : t('{n} jour(s) ouvré(s)', { n: demande.nb_jours_ouvres })}
          </p>
          {demande.est_maternite && (
            <p>
              <strong>{t('Durée :')}</strong> {t('{n} mois', { n: demande.duree_maternite_mois })} · {t('reprise le {date}', { date: versFr(demande.date_retour) })}
            </p>
          )}
          {demande.motif && <p><strong>{t('Motif :')}</strong> {demande.motif}</p>}
          <p><Justificatif demande={demande} /></p>
        </Carte>
      </div>

      <Carte titre={t('Historique des validations')}>
        {demande.validations.length === 0 ? (
          <p className="texte-discret">{t('Aucune validation enregistrée pour l’instant.')}</p>
        ) : (
          <ul className="historique-validations">
            {demande.validations.map((v) => (
              <li key={v.id}>
                <strong>{v.niveau === 'MANAGER' ? t('Chef de département') : t('Direction Générale')}</strong>
                {' — '}
                {t(v.commentaire ? '{decision} par {nom} : « {commentaire} »' : '{decision} par {nom}', { decision: v.decision === 'APPROUVE' ? t('Approuvé') : t('Refusé'), nom: v.auteur_nom || t('un compte supprimé'), commentaire: v.commentaire })}
              </li>
            ))}
          </ul>
        )}
      </Carte>

      {actionPath && <FormulaireDecision demande={demande} actionPath={actionPath} onDecidee={surDecision} />}

      {peutAnnuler && (
        <div>
          <Alerte type="erreur">{erreurAction}</Alerte>
          <button className="bouton bouton--danger" onClick={annuler}>{t('Annuler cette demande')}</button>
        </div>
      )}

      {profil.role === 'MANAGER' && !actionPath && demande.statut !== 'EN_ATTENTE_MANAGER' && (
        <p className="texte-discret"><Link to="/validations/manager">{t('Retour aux demandes à valider')}</Link></p>
      )}
    </div>
  )
}
