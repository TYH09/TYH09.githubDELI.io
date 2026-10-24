import { useCallback, useEffect, useMemo, useState } from 'react'
import { listerTout, default as api, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useAuth } from '../auth/AuthContext'
import RoleBadge from '../components/RoleBadge'

const ROLES = [
  ['EMPLOYE', 'Employé'],
  ['MANAGER', 'Manager / chef de département'],
  ['DIRECTEUR', 'Direction Générale'],
  ['RH', 'Responsable RH'],
  ['ADMINISTRATEUR', 'Administrateur'],
]
const FONCTIONS_DIRECTION = ['DQN', 'DU', 'DAF', 'DGA', 'DG']
const SEXES = [['M', 'Masculin'], ['F', 'Féminin']]

const ORDRE_ROLES = ROLES.map(([valeur]) => valeur)
const AUJOURDHUI = new Date().toISOString().slice(0, 10)
const JOURS_CONGE_ANNUEL = 18
const JOURS_CONGE_ANNUEL_MAJORE = 21
const AGE_MAX_ENFANT_MAJORATION = 6

/** Jours de congé annuel par an : 21 pour une femme dont le dernier enfant a 6 ans ou moins, sinon 18. */
function droitAnnuel(form) {
  const age = Number(form.age_dernier_enfant)
  const majore = form.sexe === 'F' && form.a_enfant === 'oui' && form.age_dernier_enfant !== '' && age <= AGE_MAX_ENFANT_MAJORATION
  return majore ? JOURS_CONGE_ANNUEL_MAJORE : JOURS_CONGE_ANNUEL
}

/** Années révolues depuis une date « AAAA-MM-JJ » (null si absente). */
function anciennete(dateIso) {
  if (!dateIso) return null
  const [annee, mois, jour] = dateIso.split('-').map(Number)
  const t = new Date()
  let annees = t.getFullYear() - annee
  if (t.getMonth() + 1 < mois || (t.getMonth() + 1 === mois && t.getDate() < jour)) annees -= 1
  return Math.max(annees, 0)
}

function libelleAnciennete(annees) {
  if (annees === null) return null
  if (annees < 1) return 'moins d’un an'
  return `${annees} an${annees > 1 ? 's' : ''}`
}

/** Comparateurs du tri de l'annuaire (le nom sert toujours de critère secondaire). */
const parNom = (a, b) => `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`, 'fr')
const COMPARATEURS = {
  nom: parNom,
  departement: (a, b) => {
    const da = a.departement_nom || ''
    const db = b.departement_nom || ''
    if (!da || !db) return da ? -1 : db ? 1 : 0 // les comptes sans département en dernier
    return da.localeCompare(db, 'fr')
  },
  role: (a, b) => ORDRE_ROLES.indexOf(a.role) - ORDRE_ROLES.indexOf(b.role),
}

/** En-tête de colonne cliquable : trie l'annuaire sur ce critère (un 2e clic inverse l'ordre). */
function EnteteTriable({ cle, tri, onTrier, children }) {
  const actif = tri.cle === cle
  return (
    <th aria-sort={actif ? (tri.sens === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="tri" onClick={() => onTrier(cle)} title={`Trier par ${children.toLowerCase()}`}>
        {children}
        <span className="tri__fleche">{actif ? (tri.sens === 1 ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  )
}

const VIDE = {
  username: '', password: '', first_name: '', last_name: '', email: '', telephone: '', date_embauche: '', matricule: '',
  sexe: '', a_enfant: '', age_dernier_enfant: '', role: 'EMPLOYE', fonction_direction: '', departement: '',
  departements_supervises: [], actif: true,
}

/** Remplit le formulaire d'édition depuis un compte existant (mot de passe vide = inchangé). */
function versFormulaire(u) {
  return {
    username: u.username, password: '', first_name: u.first_name, last_name: u.last_name,
    email: u.email || '', telephone: u.telephone || '', date_embauche: u.date_embauche || '', matricule: u.matricule, sexe: u.sexe || '', role: u.role,
    a_enfant: u.a_enfant === true ? 'oui' : u.a_enfant === false ? 'non' : '',
    age_dernier_enfant: u.age_dernier_enfant ?? '',
    fonction_direction: u.fonction_direction || '', departement: u.departement || '',
    departements_supervises: (u.departements_supervises || []).map((d) => d.id), actif: u.actif,
  }
}

/**
 * Formulaire commun à la création et à la modification d'un compte.
 * En modification, l'Administrateur peut changer nom, prénom, identifiant,
 * e-mail, matricule, sexe, rôle, département et mot de passe.
 */
function FormulaireUtilisateur({ initial, departements, modification, onSoumis, onAnnuler }) {
  const [form, setForm] = useState(initial)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const maj = (champ) => (e) => setForm({ ...form, [champ]: e.target.value })

  function basculerDepartement(id) {
    const deja = form.departements_supervises.includes(id)
    setForm({
      ...form,
      departements_supervises: deja
        ? form.departements_supervises.filter((x) => x !== id)
        : [...form.departements_supervises, id],
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    const estDirecteur = form.role === 'DIRECTEUR'
    const employee = form.role === 'EMPLOYE' && form.sexe === 'F'
    const charge = {
      username: form.username,
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      telephone: form.telephone.trim(),
      date_embauche: form.date_embauche || null,
      matricule: form.matricule,
      sexe: form.sexe,
      a_enfant: employee ? form.a_enfant === 'oui' : null,
      age_dernier_enfant: employee && form.a_enfant === 'oui' ? Number(form.age_dernier_enfant) : null,
      role: form.role,
      fonction_direction: estDirecteur ? form.fonction_direction : null,
      departement: form.departement || null,
      departements_supervises: estDirecteur ? form.departements_supervises : [],
    }
    if (form.password) charge.password = form.password
    if (modification) charge.actif = form.actif
    try {
      await onSoumis(charge)
    } catch (err) {
      setErreur(messageErreur(err))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className="formulaire" onSubmit={handleSubmit}>
      <div className="formulaire__ligne">
        <label>Identifiant<input required value={form.username} onChange={maj('username')} /></label>
        <label>
          {modification ? 'Nouveau mot de passe (laisser vide pour ne pas le changer)' : 'Mot de passe'}
          <input
            type="password" required={!modification} autoComplete="new-password"
            value={form.password} onChange={maj('password')}
          />
        </label>
      </div>
      <div className="formulaire__ligne">
        <label>Prénom<input required value={form.first_name} onChange={maj('first_name')} /></label>
        <label>Nom<input required value={form.last_name} onChange={maj('last_name')} /></label>
      </div>
      <div className="formulaire__ligne">
        <label>E-mail<input type="email" value={form.email} onChange={maj('email')} /></label>
        <label>
          Téléphone (facultatif)
          <input
            type="tel" value={form.telephone} onChange={maj('telephone')}
            placeholder="+237 6 70 12 34 56" maxLength={20}
          />
        </label>
      </div>
      <div className="formulaire__ligne">
        <label>Matricule<input required value={form.matricule} onChange={maj('matricule')} /></label>
        <label>
          Sexe
          <select required value={form.sexe} onChange={maj('sexe')}>
            <option value="" disabled>— Choisir —</option>
            {SEXES.map(([v, l]) => <option key={v} value={v}>{l} ({v})</option>)}
          </select>
        </label>
      </div>
      <div className="formulaire__ligne">
        <label>
          Rôle
          <select value={form.role} onChange={maj('role')}>
            {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        {form.role === 'DIRECTEUR' && (
          <label>
            Fonction de direction
            <select required value={form.fonction_direction} onChange={maj('fonction_direction')}>
              <option value="" disabled>— Choisir —</option>
              {FONCTIONS_DIRECTION.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
        )}
        <label>
          Département
          <select value={form.departement} onChange={maj('departement')}>
            <option value="">—</option>
            {departements.map((d) => <option key={d.id} value={d.id}>{d.nom}</option>)}
          </select>
        </label>
      </div>

      {form.role === 'EMPLOYE' && (
        <>
          <div className="formulaire__ligne">
            <label>
              Date d’entrée à l’usine
              <input
                type="date" required max={AUJOURDHUI}
                value={form.date_embauche} onChange={maj('date_embauche')}
              />
            </label>
            <p className="texte-discret formulaire__aide">
              {form.date_embauche
                ? (anciennete(form.date_embauche) >= 1
                  ? `Ancienneté : ${libelleAnciennete(anciennete(form.date_embauche))} — droit à ${droitAnnuel(form)} jours de congé annuel par an.`
                  : 'Moins d’un an d’ancienneté : pas de solde de congé annuel pour le moment (il sera attribué au premier anniversaire).')
                : 'L’ancienneté détermine le droit au congé annuel : 18 jours par an à partir d’un an d’ancienneté (21 jours pour une femme dont le dernier enfant a 6 ans ou moins).'}
            </p>
          </div>

          {form.sexe === 'F' && (
            <fieldset className="formulaire__groupe">
              <legend>Situation familiale de l’employée</legend>
              <div className="formulaire__ligne">
                <div className="choix" role="radiogroup" aria-label="A un enfant">
                  <span className="choix__titre">A-t-elle un enfant ?</span>
                  <label className="case-a-cocher">
                    <input
                      type="radio" name="a_enfant" value="oui" required
                      checked={form.a_enfant === 'oui'} onChange={maj('a_enfant')}
                    />
                    Oui
                  </label>
                  <label className="case-a-cocher">
                    <input
                      type="radio" name="a_enfant" value="non"
                      checked={form.a_enfant === 'non'}
                      onChange={(e) => setForm({ ...form, a_enfant: e.target.value, age_dernier_enfant: '' })}
                    />
                    Non
                  </label>
                </div>
                {form.a_enfant === 'oui' && (
                  <label>
                    Âge du dernier enfant (en années, 0 s’il a moins d’un an)
                    <input
                      type="number" min="0" max="40" step="1" required
                      value={form.age_dernier_enfant} onChange={maj('age_dernier_enfant')}
                    />
                  </label>
                )}
              </div>
              <p className="texte-discret">
                Dernier enfant de 6 ans ou moins : 21 jours de congé annuel par an ; sinon 18 jours
                (dans les deux cas, à partir d’un an d’ancienneté).
              </p>
            </fieldset>
          )}
        </>
      )}

      {form.role === 'DIRECTEUR' && (
        <fieldset className="formulaire__groupe">
          <legend>Départements supervisés (un directeur peut en superviser plusieurs)</legend>
          <div className="formulaire__ligne">
            {departements.map((d) => (
              <label key={d.id} className="case-a-cocher">
                <input
                  type="checkbox"
                  checked={form.departements_supervises.includes(d.id)}
                  onChange={() => basculerDepartement(d.id)}
                />
                {d.nom}
                {d.directeur && d.directeur_nom && !form.departements_supervises.includes(d.id) && (
                  <span className="texte-discret"> (actuellement : {d.directeur_nom})</span>
                )}
              </label>
            ))}
            {departements.length === 0 && <span className="texte-discret">Aucun département créé.</span>}
          </div>
        </fieldset>
      )}

      {modification && (
        <label className="case-a-cocher">
          <input
            type="checkbox" checked={form.actif}
            onChange={(e) => setForm({ ...form, actif: e.target.checked })}
          />
          Compte actif (décocher pour empêcher la connexion)
        </label>
      )}

      <Alerte type="erreur">{erreur}</Alerte>
      <div className="tableau__actions">
        <button className="bouton bouton--primaire" type="submit" disabled={enCours}>
          {modification ? 'Enregistrer les modifications' : 'Créer le compte'}
        </button>
        {onAnnuler && (
          <button type="button" className="bouton bouton--discret" onClick={onAnnuler}>Annuler</button>
        )}
      </div>
    </form>
  )
}

export default function UtilisateursPage() {
  const [utilisateurs, setUtilisateurs] = useState(null)
  const [departements, setDepartements] = useState([])
  const [afficherCreation, setAfficherCreation] = useState(false)
  const { profil } = useAuth()
  const [enEdition, setEnEdition] = useState(null)
  const [message, setMessage] = useState('')
  const [erreurSuppression, setErreurSuppression] = useState('')
  const [tri, setTri] = useState({ cle: 'nom', sens: 1 })

  const charger = useCallback(async () => {
    const [u, d] = await Promise.all([listerTout('/utilisateurs/'), listerTout('/departements/')])
    setUtilisateurs(u)
    setDepartements(d)
  }, [])

  useEffect(() => {
    let actif = true
    Promise.all([listerTout('/utilisateurs/'), listerTout('/departements/')]).then(([u, d]) => {
      if (!actif) return
      setUtilisateurs(u)
      setDepartements(d)
    })
    return () => { actif = false }
  }, [])

  async function creer(charge) {
    await api.post('/utilisateurs/', charge)
    setAfficherCreation(false)
    setMessage('Compte créé.')
    await charger()
  }

  async function modifier(charge) {
    await api.patch(`/utilisateurs/${enEdition.id}/`, charge)
    setEnEdition(null)
    setMessage('Compte mis à jour.')
    await charger()
  }

  const utilisateursTries = useMemo(() => {
    if (!utilisateurs) return null
    const comparateur = COMPARATEURS[tri.cle]
    return [...utilisateurs].sort((a, b) => tri.sens * comparateur(a, b) || parNom(a, b))
  }, [utilisateurs, tri])

  function trierPar(cle) {
    setTri((actuel) => (actuel.cle === cle ? { cle, sens: -actuel.sens } : { cle, sens: 1 }))
  }

  async function supprimer(u) {
    const ok = window.confirm(
      `Supprimer définitivement le compte de ${u.first_name} ${u.last_name} (${u.username}) ?\n\n` +
      'Ses demandes de congé, ses soldes et ses notifications seront aussi supprimés. ' +
      'Cette action est irréversible. Pour conserver l’historique, désactivez plutôt le compte.'
    )
    if (!ok) return
    setErreurSuppression('')
    setMessage('')
    try {
      await api.delete(`/utilisateurs/${u.id}/`)
      if (enEdition?.id === u.id) setEnEdition(null)
      await charger()  // le message n'apparaît qu'une fois l'annuaire à jour
      setMessage(`Compte de ${u.first_name} ${u.last_name} supprimé.`)
    } catch (err) {
      setErreurSuppression(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <div className="page__entete">
        <h1>Comptes utilisateurs</h1>
        <button
          className="bouton bouton--primaire"
          onClick={() => { setAfficherCreation(!afficherCreation); setEnEdition(null); setMessage('') }}
        >
          {afficherCreation ? 'Fermer' : '+ Nouveau compte'}
        </button>
      </div>

      <Alerte type="succes">{message}</Alerte>
      <Alerte type="erreur">{erreurSuppression}</Alerte>

      {afficherCreation && (
        <Carte titre="Créer un compte">
          <FormulaireUtilisateur
            initial={VIDE} departements={departements} modification={false}
            onSoumis={creer} onAnnuler={() => setAfficherCreation(false)}
          />
        </Carte>
      )}

      {enEdition && (
        <Carte titre={`Modifier le compte de ${enEdition.first_name} ${enEdition.last_name}`}>
          <FormulaireUtilisateur
            key={enEdition.id}
            initial={versFormulaire(enEdition)} departements={departements} modification
            onSoumis={modifier} onAnnuler={() => setEnEdition(null)}
          />
        </Carte>
      )}

      <Carte titre="Annuaire">
        {utilisateurs === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead>
              <tr>
                <EnteteTriable cle="nom" tri={tri} onTrier={trierPar}>Nom</EnteteTriable><th>Identifiant</th><th>Matricule</th><th>Sexe</th>
                <EnteteTriable cle="role" tri={tri} onTrier={trierPar}>Rôle</EnteteTriable>
                <EnteteTriable cle="departement" tri={tri} onTrier={trierPar}>Département</EnteteTriable>
                <th>Ancienneté</th><th>Supervise</th><th>Actif</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {utilisateursTries.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.first_name} {u.last_name}
                    <br /><span className="texte-discret">{u.email}</span>
                    <br /><span className="texte-discret">{u.telephone || 'téléphone non renseigné'}</span>
                  </td>
                  <td>{u.username}</td>
                  <td>{u.matricule}</td>
                  <td>{u.sexe || '—'}</td>
                  <td>
                    <RoleBadge role={u.role} />
                    {u.fonction_direction && <span className="texte-discret"> {u.fonction_direction}</span>}
                  </td>
                  <td>{u.departement_nom || '—'}</td>
                  <td>
                    {u.role === 'EMPLOYE' ? (
                      u.anciennete_annees === null ? (
                        <span className="texte-discret">date non renseignée</span>
                      ) : (
                        <>
                          {libelleAnciennete(u.anciennete_annees)}
                          <br />
                          <span className={`badge ${u.eligible_conge_annuel ? 'badge--a-venir' : 'badge--en-conge'}`}>
                            {u.eligible_conge_annuel ? `Congé annuel · ${u.droit_conge_annuel} j` : 'Pas de solde'}
                          </span>
                        </>
                      )
                    ) : '—'}
                  </td>
                  <td>
                    {u.role === 'DIRECTEUR'
                      ? (u.departements_supervises.map((d) => d.nom).join(', ') || '—')
                      : ''}
                  </td>
                  <td>{u.actif ? 'Oui' : 'Non'}</td>
                  <td className="tableau__actions">
                    <button
                      className="bouton bouton--discret"
                      onClick={() => { setEnEdition(u); setAfficherCreation(false); setMessage(''); setErreurSuppression(''); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                    >
                      Modifier
                    </button>
                    {u.id !== profil.id && (
                      <button className="bouton bouton--danger" onClick={() => supprimer(u)}>
                        Supprimer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
