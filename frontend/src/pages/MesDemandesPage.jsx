import { useEffect, useState } from 'react'
import api, { listerTout, messageErreur } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import StatutBadge from '../components/StatutBadge'
import Justificatif from '../components/Justificatif'
import { ajouterJours, dateDeRetour, dateFinPaternite, versFr } from '../utils/dates'
import { useI18n } from '../i18n/I18nContext'

const STATUTS_ANNULABLES = ['BROUILLON', 'EN_ATTENTE_MANAGER', 'EN_ATTENTE_DIRECTION']

// Congé de maternité : 3 mois par an (90 jours calendaires, 30 jours décomptés par mois), pris en
// 1, 2 ou 3 mois à la fois selon ce qu'il reste. Mêmes valeurs que le serveur.
const JOURS_PAR_MOIS_MATERNITE = 30
const DUREES_MATERNITE = [1, 2, 3]

function FormulaireNouvelleDemande({ typesConge, onCree }) {
  const { t } = useI18n()
  const { profil } = useAuth()
  // Les congés réservés à un sexe (maternité : F, paternité : M) ne sont pas
  // proposés à l'autre sexe. L'API refuse de toute façon la demande (règle métier).
  const typesProposes = typesConge.filter((tc) => !tc.reserve_a_sexe || tc.reserve_a_sexe === profil.sexe)
  const [typeConge, setTypeConge] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [dureeMois, setDureeMois] = useState(0)
  const [soldeMaternite, setSoldeMaternite] = useState(null)
  const [feries, setFeries] = useState([])
  const [motif, setMotif] = useState('')
  const [fichier, setFichier] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const typeSelectionne = typesConge.find((tc) => String(tc.id) === String(typeConge))
  const estMaternite = !!typeSelectionne?.est_maternite
  const estPaternite = !!typeSelectionne?.est_paternite
  // Sans ancienneté suffisante (moins d'un an), pas de solde donc pas de congé annuel.
  // La maternité a son propre solde (90 jours) sans condition d'ancienneté.
  // L'API applique les mêmes règles ; ce message évite simplement un aller-retour.
  const sansDroitAuSolde = !!typeSelectionne?.decompte_solde && !estMaternite && !profil.eligible_conge_annuel

  // Les jours fériés servent uniquement à afficher la date de retour (le serveur recalcule).
  useEffect(() => {
    if ((estMaternite || estPaternite) && feries.length === 0) {
      listerTout('/jours-feries/').then(setFeries).catch(() => {})
    }
  }, [estMaternite, estPaternite, feries.length])

  // Solde de maternité de l'année du départ : il indique les durées encore disponibles
  // (3 mois par an : après 1 mois il reste 1 ou 2 mois, après 2 mois il reste 1 mois, après 3 mois plus rien).
  const anneeDepart = dateDebut ? Number(dateDebut.slice(0, 4)) : null
  useEffect(() => {
    if (!estMaternite || !anneeDepart) return undefined
    let annule = false
    api.get('/soldes/', { params: { annee: anneeDepart, type_conge: typeSelectionne.id } })
      .then(({ data }) => { if (!annule) setSoldeMaternite(data.results?.[0] ?? null) })
      .catch(() => { if (!annule) setSoldeMaternite(null) })
    return () => { annule = true }
  }, [estMaternite, anneeDepart, typeSelectionne?.id])

  const dureesDisponibles = estMaternite
    ? (soldeMaternite && soldeMaternite.annee === anneeDepart ? soldeMaternite.mois_disponibles : DUREES_MATERNITE)
    : []
  const dureeEffective = dureesDisponibles.includes(dureeMois) ? dureeMois : 0
  const plusDeMaternite = estMaternite && !!dateDebut && dureesDisponibles.length === 0
  // Paternité : 3 jours ouvrés maximum, la date de fin et la date de retour découlent de la date de départ.
  const calculPaternite = estPaternite && dateDebut
    ? (() => {
      const fin = dateFinPaternite(dateDebut, feries)
      return { fin, retour: dateDeRetour(fin, feries) }
    })()
    : null
  const calculMaternite = estMaternite && dateDebut && dureeEffective
    ? (() => {
      const jours = dureeEffective * JOURS_PAR_MOIS_MATERNITE
      const fin = ajouterJours(dateDebut, jours - 1)
      return { jours, fin, retour: dateDeRetour(fin, feries) }
    })()
    : null

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const formData = new FormData()
      formData.append('type_conge', typeConge)
      formData.append('date_debut', dateDebut)
      if (estMaternite) formData.append('duree_maternite_mois', String(dureeEffective))
      else if (!estPaternite) formData.append('date_fin', dateFin)
      formData.append('motif', motif)
      if (fichier) formData.append('justificatif_fichier', fichier)

      const { data } = await api.post('/demandes/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onCree(data)
      setTypeConge('')
      setDateDebut('')
      setDateFin('')
      setDureeMois(0)
      setMotif('')
      setFichier(null)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Carte titre={t('Nouvelle demande de congé')}>
      <form className="formulaire" onSubmit={handleSubmit}>
        <label>
          {t('Type de congé')}
          <select value={typeConge} onChange={(e) => setTypeConge(e.target.value)} required>
            <option value="" disabled>{t('— Choisir —')}</option>
            {typesProposes.map((tc) => (
              <option key={tc.id} value={tc.id}>{t(tc.libelle)}</option>
            ))}
          </select>
        </label>
        <div className="formulaire__ligne">
          <label>
            {t('Date de début')}
            <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} required />
          </label>
          {!estMaternite && !estPaternite && (
            <label>
              {t('Date de fin')}
              <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} required />
            </label>
          )}
        </div>
        {calculPaternite && (
          <Alerte type="info">
            {t('Congé de paternité : 3 jours ouvrés au maximum. Fin du congé :')} <strong>{versFr(calculPaternite.fin)}</strong>
            {' · '}{t('reprise du travail :')} <strong>{versFr(calculPaternite.retour)}</strong>.
          </Alerte>
        )}
        {estMaternite && (
          <fieldset className="choix">
            <legend className="choix__titre">{t('Durée du congé de maternité (3 mois par an au total)')}</legend>
            {DUREES_MATERNITE.map((m) => {
              const disponible = dureesDisponibles.includes(m)
              return (
                <label key={m} className={disponible ? '' : 'choix--indisponible'}>
                  <input
                    type="radio" name="duree_maternite" value={m} disabled={!disponible}
                    checked={dureeEffective === m} onChange={() => setDureeMois(m)} required
                  />
                  {t('{m} mois', { m })}{!disponible && ` ${t('(indisponible : solde insuffisant)')}`}
                </label>
              )
            })}
            <p className="texte-discret">
              {t('Indiquez votre date de départ : la date de fin et la date de retour sont calculées automatiquement. Si vous prenez 1 mois, il vous restera 1 ou 2 mois ; après 2 mois, il vous restera 1 mois ; après 3 mois, le congé de maternité n’est plus disponible cette année.')}
            </p>
            {plusDeMaternite && (
              <Alerte type="erreur">
                {t('Vous avez déjà pris ou demandé les 3 mois de congé de maternité pour {annee} : il n’est plus disponible cette année.', { annee: anneeDepart })}
              </Alerte>
            )}
            {calculMaternite && (
              <Alerte type="info">
                {t('Fin du congé :')} <strong>{versFr(calculMaternite.fin)}</strong> · {t('reprise du travail :')}{' '}
                <strong>{versFr(calculMaternite.retour)}</strong>.<br />
                {t('{jours} jours décomptés de votre solde de maternité', { jours: calculMaternite.jours })}
                {soldeMaternite && ` ${t('({jours} j. disponibles avant cette demande)', { jours: soldeMaternite.jours_disponibles })}`}.
              </Alerte>
            )}
          </fieldset>
        )}
        <label>
          {t('Motif (optionnel)')}
          <input type="text" value={motif} onChange={(e) => setMotif(e.target.value)} maxLength={255} />
        </label>
        <label>
          {t('Justificatif (PDF, PNG ou JPEG, 5 Mo max)')} {typeSelectionne?.justificatif_obligatoire && t('(obligatoire pour ce type)')}
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFichier(e.target.files[0] || null)} />
        </label>

        {sansDroitAuSolde && (
          <Alerte type="info">
            {profil.date_embauche === null
              ? t('Votre date d’entrée à l’usine n’est pas renseignée : vous ne disposez pas de solde de congé annuel. Contactez l’administrateur.')
              : t('Vous n’avez pas encore un an d’ancienneté : vous ne disposez pas de solde de congé annuel pour le moment.')}
          </Alerte>
        )}
        <Alerte type="erreur">{erreur}</Alerte>

        <button className="bouton bouton--primaire" type="submit" disabled={enCours || sansDroitAuSolde || (estMaternite && !dureeEffective)}>
          {enCours ? t('Envoi…') : t('Soumettre la demande')}
        </button>
      </form>
    </Carte>
  )
}

function LigneDemande({ demande, onAnnulee }) {
  const { t } = useI18n()
  const [ouvert, setOuvert] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  async function annuler() {
    if (!window.confirm(t('Confirmer l’annulation de cette demande ?'))) return
    setEnCours(true)
    setErreur('')
    try {
      const { data } = await api.post(`/demandes/${demande.id}/annuler/`)
      onAnnulee(data)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <>
      <tr>
        <td>{t(demande.type_conge_libelle)}</td>
        <td>{demande.date_debut} → {demande.date_fin}</td>
        <td>
          {demande.est_maternite ? t('{n} (calendaires)', { n: demande.nb_jours_decomptes }) : demande.nb_jours_ouvres}
        </td>
        <td><StatutBadge statut={demande.statut} /></td>
        <td className="tableau__actions">
          <button className="bouton bouton--discret" onClick={() => setOuvert(!ouvert)}>
            {ouvert ? t('Masquer') : t('Détails')}
          </button>
          {STATUTS_ANNULABLES.includes(demande.statut) && (
            <button className="bouton bouton--danger" onClick={annuler} disabled={enCours}>
              {t('Annuler')}
            </button>
          )}
        </td>
      </tr>
      {ouvert && (
        <tr className="tableau__sous-ligne">
          <td colSpan={5}>
            {demande.motif && <p><strong>{t('Motif :')}</strong> {demande.motif}</p>}
            {demande.est_maternite && (
              <p>
                <strong>{t('Durée :')}</strong> {t('{n} mois', { n: demande.duree_maternite_mois })} · {t('reprise le {date}', { date: versFr(demande.date_retour) })}
              </p>
            )}
            {demande.a_justificatif && <p><Justificatif demande={demande} /></p>}
            <Alerte type="erreur">{erreur}</Alerte>
            {demande.validations.length === 0 ? (
              <p className="texte-discret">{t('Aucune validation enregistrée pour l’instant.')}</p>
            ) : (
              <ul className="historique-validations">
                {demande.validations.map((v) => (
                  <li key={v.id}>
                    <strong>{v.niveau === 'MANAGER' ? t('Chef de département') : t('Direction Générale')}</strong>
                    {' — '}
                    {t(v.commentaire ? '{decision} par {nom} : « {commentaire} »' : '{decision} par {nom}', { decision: v.decision === 'APPROUVE' ? t('Approuvé') : t('Refusé'), nom: v.auteur_nom, commentaire: v.commentaire })}
                  </li>
                ))}
              </ul>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export default function MesDemandesPage() {
  const { t } = useI18n()
  const { rafraichirProfil } = useAuth()
  const [typesConge, setTypesConge] = useState([])
  const [demandes, setDemandes] = useState(null)
  const [afficherFormulaire, setAfficherFormulaire] = useState(false)

  useEffect(() => {
    api.get('/types-conge/').then(({ data }) => setTypesConge(data.results))
    listerTout('/demandes/', { mes: 1 }).then(setDemandes)
  }, [])

  function surDemandeCreee(nouvelle) {
    setDemandes((prev) => [nouvelle, ...prev])
    setAfficherFormulaire(false)
  }

  function surDemandeAnnulee(maj) {
    setDemandes((prev) => prev.map((d) => (d.id === maj.id ? maj : d)))
    rafraichirProfil()
  }

  return (
    <div className="page">
      <div className="page__entete">
        <h1>{t('Mes demandes de congé')}</h1>
        <button className="bouton bouton--primaire" onClick={() => setAfficherFormulaire(!afficherFormulaire)}>
          {afficherFormulaire ? t('Fermer') : t('+ Nouvelle demande')}
        </button>
      </div>

      {afficherFormulaire && <FormulaireNouvelleDemande typesConge={typesConge} onCree={surDemandeCreee} />}

      <Carte titre={t('Historique')}>
        {demandes === null ? (
          <Chargement />
        ) : demandes.length === 0 ? (
          <p className="texte-discret">{t('Vous n’avez encore soumis aucune demande.')}</p>
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>{t('Type')}</th><th>{t('Période')}</th><th>{t('Jours décomptés')}</th><th>{t('Statut')}</th><th>{t('Actions')}</th></tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <LigneDemande key={d.id} demande={d} onAnnulee={surDemandeAnnulee} />
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
