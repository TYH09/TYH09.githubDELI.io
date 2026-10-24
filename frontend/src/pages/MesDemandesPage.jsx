import { useEffect, useState } from 'react'
import api, { listerTout, messageErreur } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import StatutBadge from '../components/StatutBadge'
import Justificatif from '../components/Justificatif'
import { ajouterJours, dateDeRetour, versFr } from '../utils/dates'

const STATUTS_ANNULABLES = ['BROUILLON', 'EN_ATTENTE_MANAGER', 'EN_ATTENTE_DIRECTION']

// Congé de maternité : 3 mois par an (90 jours calendaires, 30 jours décomptés par mois), pris en
// 1, 2 ou 3 mois à la fois selon ce qu'il reste. Mêmes valeurs que le serveur.
const JOURS_PAR_MOIS_MATERNITE = 30
const DUREES_MATERNITE = [1, 2, 3]

function FormulaireNouvelleDemande({ typesConge, onCree }) {
  const { profil } = useAuth()
  // Les congés réservés à un sexe (maternité : F, paternité : M) ne sont pas
  // proposés à l'autre sexe. L'API refuse de toute façon la demande (règle métier).
  const typesProposes = typesConge.filter((t) => !t.reserve_a_sexe || t.reserve_a_sexe === profil.sexe)
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

  const typeSelectionne = typesConge.find((t) => String(t.id) === String(typeConge))
  const estMaternite = !!typeSelectionne?.est_maternite
  // Sans ancienneté suffisante (moins d'un an), pas de solde donc pas de congé annuel.
  // La maternité a son propre solde (90 jours) sans condition d'ancienneté.
  // L'API applique les mêmes règles ; ce message évite simplement un aller-retour.
  const sansDroitAuSolde = !!typeSelectionne?.decompte_solde && !estMaternite && !profil.eligible_conge_annuel

  // Les jours fériés servent uniquement à afficher la date de retour (le serveur recalcule).
  useEffect(() => {
    if (estMaternite && feries.length === 0) {
      listerTout('/jours-feries/').then(setFeries).catch(() => {})
    }
  }, [estMaternite, feries.length])

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
      else formData.append('date_fin', dateFin)
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
    <Carte titre="Nouvelle demande de congé">
      <form className="formulaire" onSubmit={handleSubmit}>
        <label>
          Type de congé
          <select value={typeConge} onChange={(e) => setTypeConge(e.target.value)} required>
            <option value="" disabled>— Choisir —</option>
            {typesProposes.map((t) => (
              <option key={t.id} value={t.id}>{t.libelle}</option>
            ))}
          </select>
        </label>
        <div className="formulaire__ligne">
          <label>
            Date de début
            <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} required />
          </label>
          {!estMaternite && (
            <label>
              Date de fin
              <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} required />
            </label>
          )}
        </div>
        {estMaternite && (
          <fieldset className="choix">
            <legend className="choix__titre">Durée du congé de maternité (3 mois par an au total)</legend>
            {DUREES_MATERNITE.map((m) => {
              const disponible = dureesDisponibles.includes(m)
              return (
                <label key={m} className={disponible ? '' : 'choix--indisponible'}>
                  <input
                    type="radio" name="duree_maternite" value={m} disabled={!disponible}
                    checked={dureeEffective === m} onChange={() => setDureeMois(m)} required
                  />
                  {m} mois{!disponible && ' (indisponible : solde insuffisant)'}
                </label>
              )
            })}
            <p className="texte-discret">
              Indiquez votre date de départ : la date de fin et la date de retour sont calculées automatiquement.
              Si vous prenez 1 mois, il vous restera 1 ou 2 mois ; après 2 mois, il vous restera 1 mois ;
              après 3 mois, le congé de maternité n’est plus disponible cette année.
            </p>
            {plusDeMaternite && (
              <Alerte type="erreur">
                Vous avez déjà pris ou demandé les 3 mois de congé de maternité pour {anneeDepart} : il n’est plus disponible cette année.
              </Alerte>
            )}
            {calculMaternite && (
              <Alerte type="info">
                Fin du congé : <strong>{versFr(calculMaternite.fin)}</strong> · reprise du travail :{' '}
                <strong>{versFr(calculMaternite.retour)}</strong>.<br />
                {calculMaternite.jours} jours décomptés de votre solde de maternité
                {soldeMaternite && ` (${soldeMaternite.jours_disponibles} j. disponibles avant cette demande)`}.
              </Alerte>
            )}
          </fieldset>
        )}
        <label>
          Motif (optionnel)
          <input type="text" value={motif} onChange={(e) => setMotif(e.target.value)} maxLength={255} />
        </label>
        <label>
          Justificatif (PDF, PNG ou JPEG, 5 Mo max) {typeSelectionne?.justificatif_obligatoire && '(obligatoire pour ce type)'}
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFichier(e.target.files[0] || null)} />
        </label>

        {sansDroitAuSolde && (
          <Alerte type="info">
            {profil.date_embauche === null
              ? 'Votre date d’entrée à l’usine n’est pas renseignée : vous ne disposez pas de solde de congé annuel. Contactez l’administrateur.'
              : 'Vous n’avez pas encore un an d’ancienneté : vous ne disposez pas de solde de congé annuel pour le moment.'}
          </Alerte>
        )}
        <Alerte type="erreur">{erreur}</Alerte>

        <button className="bouton bouton--primaire" type="submit" disabled={enCours || sansDroitAuSolde || (estMaternite && !dureeEffective)}>
          {enCours ? 'Envoi…' : 'Soumettre la demande'}
        </button>
      </form>
    </Carte>
  )
}

function LigneDemande({ demande, onAnnulee }) {
  const [ouvert, setOuvert] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  async function annuler() {
    if (!window.confirm('Confirmer l’annulation de cette demande ?')) return
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
        <td>{demande.type_conge_libelle}</td>
        <td>{demande.date_debut} → {demande.date_fin}</td>
        <td>
          {demande.est_maternite ? `${demande.nb_jours_decomptes} (calendaires)` : demande.nb_jours_ouvres}
        </td>
        <td><StatutBadge statut={demande.statut} /></td>
        <td className="tableau__actions">
          <button className="bouton bouton--discret" onClick={() => setOuvert(!ouvert)}>
            {ouvert ? 'Masquer' : 'Détails'}
          </button>
          {STATUTS_ANNULABLES.includes(demande.statut) && (
            <button className="bouton bouton--danger" onClick={annuler} disabled={enCours}>
              Annuler
            </button>
          )}
        </td>
      </tr>
      {ouvert && (
        <tr className="tableau__sous-ligne">
          <td colSpan={5}>
            {demande.motif && <p><strong>Motif :</strong> {demande.motif}</p>}
            {demande.est_maternite && (
              <p>
                <strong>Durée :</strong> {demande.duree_maternite_mois} mois · reprise le {versFr(demande.date_retour)}
              </p>
            )}
            {demande.a_justificatif && <p><Justificatif demande={demande} /></p>}
            <Alerte type="erreur">{erreur}</Alerte>
            {demande.validations.length === 0 ? (
              <p className="texte-discret">Aucune validation enregistrée pour l’instant.</p>
            ) : (
              <ul className="historique-validations">
                {demande.validations.map((v) => (
                  <li key={v.id}>
                    <strong>{v.niveau === 'MANAGER' ? 'Chef de département' : 'Direction Générale'}</strong>
                    {' — '}
                    {v.decision === 'APPROUVE' ? 'Approuvé' : 'Refusé'} par {v.auteur_nom}
                    {v.commentaire && <> : « {v.commentaire} »</>}
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
  const { rafraichirProfil } = useAuth()
  const [typesConge, setTypesConge] = useState([])
  const [demandes, setDemandes] = useState(null)
  const [afficherFormulaire, setAfficherFormulaire] = useState(false)

  useEffect(() => {
    api.get('/types-conge/').then(({ data }) => setTypesConge(data.results))
    listerTout('/demandes/').then(setDemandes)
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
        <h1>Mes demandes de congé</h1>
        <button className="bouton bouton--primaire" onClick={() => setAfficherFormulaire(!afficherFormulaire)}>
          {afficherFormulaire ? 'Fermer' : '+ Nouvelle demande'}
        </button>
      </div>

      {afficherFormulaire && <FormulaireNouvelleDemande typesConge={typesConge} onCree={surDemandeCreee} />}

      <Carte titre="Historique">
        {demandes === null ? (
          <Chargement />
        ) : demandes.length === 0 ? (
          <p className="texte-discret">Vous n’avez encore soumis aucune demande.</p>
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>Type</th><th>Période</th><th>Jours décomptés</th><th>Statut</th><th>Actions</th></tr>
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
