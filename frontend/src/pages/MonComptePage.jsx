import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import RoleBadge from '../components/RoleBadge'

export default function MonComptePage() {
  const { profil } = useAuth()
  const [ancien, setAncien] = useState('')
  const [nouveau, setNouveau] = useState('')
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur('')
    setSucces('')
    try {
      await api.post('/me/mot-de-passe/', { ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau })
      setSucces('Mot de passe mis à jour.')
      setAncien('')
      setNouveau('')
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>Mon compte</h1>
      <Carte titre="Informations">
        <p><strong>{profil.first_name} {profil.last_name}</strong> — <RoleBadge role={profil.role} /></p>
        <p className="texte-discret">{profil.email}{profil.telephone && ` · ${profil.telephone}`}</p>
        <p className="texte-discret">
          Matricule : {profil.matricule}
          {profil.sexe_affiche && ` · ${profil.sexe_affiche}`}
          {profil.departement_nom && ` · ${profil.departement_nom}`}
        </p>
        {profil.role === 'EMPLOYE' && (
          <p className="texte-discret">
            {profil.date_embauche
              ? `Entré(e) à l'usine le ${profil.date_embauche.split('-').reverse().join('/')} · ancienneté : ${
                profil.anciennete_annees < 1 ? 'moins d’un an' : `${profil.anciennete_annees} an${profil.anciennete_annees > 1 ? 's' : ''}`
              } · ${profil.eligible_conge_annuel ? `droit à ${profil.droit_conge_annuel} jours de congé annuel par an` : 'pas encore de droit au congé annuel'}`
              : 'Date d’entrée à l’usine non renseignée'}
          </p>
        )}
        {profil.role === 'EMPLOYE' && profil.sexe === 'F' && profil.a_enfant !== null && (
          <p className="texte-discret">
            {profil.a_enfant
              ? `Dernier enfant : ${profil.age_dernier_enfant} an${profil.age_dernier_enfant > 1 ? 's' : ''}`
              : 'Pas d’enfant déclaré'}
            {profil.a_enfant && profil.age_dernier_enfant <= 6 && ' (6 ans ou moins : 21 jours de congé annuel)'}
          </p>
        )}
        {profil.role === 'DIRECTEUR' && (
          <p className="texte-discret">
            Départements supervisés :{' '}
            {profil.departements_supervises.length
              ? profil.departements_supervises.map((d) => d.nom).join(', ')
              : 'aucun en particulier (vous traitez les départements sans directeur affecté)'}
          </p>
        )}
      </Carte>

      <Carte titre="Changer mon mot de passe">
        <form className="formulaire" onSubmit={handleSubmit}>
          <label>
            Mot de passe actuel
            <input type="password" required value={ancien} onChange={(e) => setAncien(e.target.value)} />
          </label>
          <label>
            Nouveau mot de passe
            <input type="password" required value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
          </label>
          <Alerte type="erreur">{erreur}</Alerte>
          <Alerte type="succes">{succes}</Alerte>
          <button className="bouton bouton--primaire" type="submit">Mettre à jour</button>
        </form>
      </Carte>
    </div>
  )
}
