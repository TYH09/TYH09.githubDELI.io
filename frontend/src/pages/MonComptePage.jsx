import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import RoleBadge from '../components/RoleBadge'
import { useI18n } from '../i18n/I18nContext'
import ChampMotDePasse from '../components/ChampMotDePasse'
import { ROLES_AVEC_CONGES } from '../utils/roles'

export default function MonComptePage() {
  const { t } = useI18n()
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
      setSucces(t('Mot de passe mis à jour.'))
      setAncien('')
      setNouveau('')
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>{t('Mon compte')}</h1>
      <Carte titre={t('Informations')}>
        <p><strong>{profil.first_name} {profil.last_name}</strong> — <RoleBadge role={profil.role} /></p>
        <p className="texte-discret">{profil.email}{profil.telephone && ` · ${profil.telephone}`}</p>
        <p className="texte-discret">
          {t('Matricule :')} {profil.matricule}
          {profil.sexe_affiche && ` · ${t(profil.sexe_affiche)}`}
          {profil.departement_nom && ` · ${profil.departement_nom}`}
        </p>
        {ROLES_AVEC_CONGES.includes(profil.role) && (
          <p className="texte-discret">
            {profil.date_embauche
              ? t('Entré(e) à l\'usine le {date} · ancienneté : {anciennete} · {droit}', {
                date: profil.date_embauche.split('-').reverse().join('/'),
                anciennete: profil.anciennete_annees < 1
                  ? t('moins d’un an')
                  : (profil.anciennete_annees > 1 ? t('{n} ans', { n: profil.anciennete_annees }) : t('{n} an', { n: profil.anciennete_annees })),
                droit: profil.eligible_conge_annuel
                  ? t('droit à {jours} jours de congé annuel par an', { jours: profil.droit_conge_annuel })
                  : t('pas encore de droit au congé annuel'),
              })
              : t('Date d’entrée à l’usine non renseignée')}
          </p>
        )}
        {ROLES_AVEC_CONGES.includes(profil.role) && profil.sexe === 'F' && profil.a_enfant !== null && (
          <p className="texte-discret">
            {profil.a_enfant
              ? (profil.age_dernier_enfant > 1
                ? t('Dernier enfant : {n} ans', { n: profil.age_dernier_enfant })
                : t('Dernier enfant : {n} an', { n: profil.age_dernier_enfant }))
              : t('Pas d’enfant déclaré')}
            {profil.a_enfant && profil.age_dernier_enfant <= 6 && ` ${t('(6 ans ou moins : 21 jours de congé annuel)')}`}
          </p>
        )}
        {profil.role === 'DIRECTEUR' && (
          <p className="texte-discret">
            {t('Départements supervisés :')}{' '}
            {profil.departements_supervises.length
              ? profil.departements_supervises.map((d) => d.nom).join(', ')
              : t('aucun en particulier (vous traitez les départements sans directeur affecté)')}
          </p>
        )}
      </Carte>

      <Carte titre={t('Changer mon mot de passe')}>
        <form className="formulaire" onSubmit={handleSubmit}>
          <label>
            {t('Mot de passe actuel')}
            <ChampMotDePasse required value={ancien} onChange={(e) => setAncien(e.target.value)} />
          </label>
          <label>
            {t('Nouveau mot de passe')}
            <ChampMotDePasse required autoComplete="new-password" value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
          </label>
          <Alerte type="erreur">{erreur}</Alerte>
          <Alerte type="succes">{succes}</Alerte>
          <button className="bouton bouton--primaire" type="submit">{t('Mettre à jour')}</button>
        </form>
      </Carte>
    </div>
  )
}
