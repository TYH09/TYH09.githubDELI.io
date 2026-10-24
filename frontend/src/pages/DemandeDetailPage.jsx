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

const STATUTS_ANNULABLES = ['BROUILLON', 'EN_ATTENTE_MANAGER', 'EN_ATTENTE_DIRECTION']

/** Formulaire de décision : visible seulement pour celui dont c'est le tour. */
function FormulaireDecision({ demande, actionPath, onDecidee }) {
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
    <Carte titre="Votre décision">
      <div className="formulaire">
        <label>
          Commentaire (optionnel)
          <input type="text" value={commentaire} maxLength={255} onChange={(e) => setCommentaire(e.target.value)} />
        </label>
        <Alerte type="erreur">{erreur}</Alerte>
        <div className="tableau__actions">
          <button className="bouton bouton--succes" disabled={!!enCours} onClick={() => decider('APPROUVE')}>
            {enCours === 'APPROUVE' ? '…' : 'Approuver'}
          </button>
          <button className="bouton bouton--danger" disabled={!!enCours} onClick={() => decider('REFUSE')}>
            {enCours === 'REFUSE' ? '…' : 'Refuser'}
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
        <h1>Demande introuvable</h1>
        <Alerte type="info">
          Cette demande n’existe pas ou n’entre pas dans votre périmètre.
        </Alerte>
        <button className="bouton bouton--discret" onClick={() => navigate(-1)}>← Retour</button>
      </div>
    )
  }
  if (erreur) return <div className="page"><Alerte type="erreur">{erreur}</Alerte></div>
  if (!demande) return <Chargement />

  const u = demande.utilisateur_detail
  const actionPath =
    profil.role === 'MANAGER' && demande.statut === 'EN_ATTENTE_MANAGER' ? 'valider-manager'
      : profil.role === 'DIRECTEUR' && demande.statut === 'EN_ATTENTE_DIRECTION' ? 'valider-direction'
        : null
  const peutAnnuler =
    demande.utilisateur === profil.id && STATUTS_ANNULABLES.includes(demande.statut)

  function surDecision(maj, decision) {
    setDemande(maj)
    setMessage(decision === 'APPROUVE' ? 'Demande approuvée.' : 'Demande refusée.')
  }

  async function annuler() {
    if (!window.confirm('Confirmer l’annulation de cette demande ?')) return
    setErreurAction('')
    try {
      const { data } = await api.post(`/demandes/${demande.id}/annuler/`)
      setDemande(data)
      setMessage('Demande annulée.')
      rafraichirProfil()
    } catch (err) {
      setErreurAction(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <div className="page__entete">
        <h1>Demande de congé n° {demande.id}</h1>
        <button className="bouton bouton--discret" onClick={() => navigate(-1)}>← Retour</button>
      </div>

      <Alerte type="succes">{message}</Alerte>

      <div className="grille-cartes">
        <Carte titre="Demandeur">
          <p><strong>{u.first_name} {u.last_name}</strong></p>
          <p className="texte-discret">{u.role_affiche}{u.departement_nom && ` · ${u.departement_nom}`}</p>
          <p className="texte-discret">
            {u.email ? <a href={`mailto:${u.email}`}>{u.email}</a> : 'e-mail non renseigné'}
            {' · '}
            {u.telephone ? <a href={`tel:${u.telephone.replace(/[^+\d]/g, '')}`}>{u.telephone}</a> : 'téléphone non renseigné'}
          </p>
        </Carte>

        <Carte titre="Demande">
          <p><strong>{demande.type_conge_libelle}</strong> <StatutBadge statut={demande.statut} /></p>
          <p>
            {demande.date_debut} → {demande.date_fin} ·{' '}
            {demande.est_maternite
              ? `${demande.nb_jours_decomptes} jours calendaires décomptés`
              : `${demande.nb_jours_ouvres} jour(s) ouvré(s)`}
          </p>
          {demande.est_maternite && (
            <p>
              <strong>Durée :</strong> {demande.duree_maternite_mois} mois · reprise le {versFr(demande.date_retour)}
            </p>
          )}
          {demande.motif && <p><strong>Motif :</strong> {demande.motif}</p>}
          <p><Justificatif demande={demande} /></p>
        </Carte>
      </div>

      <Carte titre="Historique des validations">
        {demande.validations.length === 0 ? (
          <p className="texte-discret">Aucune validation enregistrée pour l’instant.</p>
        ) : (
          <ul className="historique-validations">
            {demande.validations.map((v) => (
              <li key={v.id}>
                <strong>{v.niveau === 'MANAGER' ? 'Chef de département' : 'Direction Générale'}</strong>
                {' — '}
                {v.decision === 'APPROUVE' ? 'Approuvé' : 'Refusé'} par {v.auteur_nom || 'un compte supprimé'}
                {v.commentaire && <> : « {v.commentaire} »</>}
              </li>
            ))}
          </ul>
        )}
      </Carte>

      {actionPath && <FormulaireDecision demande={demande} actionPath={actionPath} onDecidee={surDecision} />}

      {peutAnnuler && (
        <div>
          <Alerte type="erreur">{erreurAction}</Alerte>
          <button className="bouton bouton--danger" onClick={annuler}>Annuler cette demande</button>
        </div>
      )}

      {profil.role === 'MANAGER' && !actionPath && demande.statut !== 'EN_ATTENTE_MANAGER' && (
        <p className="texte-discret"><Link to="/validations/manager">Retour aux demandes à valider</Link></p>
      )}
    </div>
  )
}
