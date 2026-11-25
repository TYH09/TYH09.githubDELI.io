import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'
import Alerte from '../components/Alerte'
import StatutBadge from '../components/StatutBadge'
import { useI18n } from '../i18n/I18nContext'
import { ROLES_AVEC_CONGES } from '../utils/roles'

function TableDemandesResume({ demandes }) {
  const { t } = useI18n()
  return (
    <table className="tableau">
      <thead>
        <tr><th>{t('Type')}</th><th>{t('Période')}</th><th>{t('Jours décomptés')}</th><th>{t('Statut')}</th></tr>
      </thead>
      <tbody>
        {demandes.map((d) => (
          <tr key={d.id}>
            <td>{t(d.type_conge_libelle)}</td>
            <td>{d.date_debut} → {d.date_fin}</td>
            <td>{d.nb_jours_decomptes}</td>
            <td><StatutBadge statut={d.statut} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// `avecDemandes` : l'employé voit aussi le résumé de ses dernières demandes ; les autres rôles
// (chef de département, RH, directeur) ont, comme sur les maquettes, uniquement leurs soldes.
function TableauEmploye({ avecDemandes = true }) {
  const { t } = useI18n()
  const { soldes, profil } = useAuth()
  const [demandes, setDemandes] = useState(null)

  useEffect(() => {
    if (avecDemandes) api.get('/demandes/', { params: { mes: 1 } }).then(({ data }) => setDemandes(data.results.slice(0, 5)))
  }, [avecDemandes])

  return (
    <>
      <div className="grille-cartes">
        {soldes.map((s) => (
          <Carte key={s.id} titre={t(s.type_conge_libelle)}>
            <p className="chiffre-cle">{s.jours_restants}<span> {t('j. restants')}</span></p>
            <p className="texte-discret">{t('{pris} pris sur {acquis} acquis ({annee})', { pris: s.jours_pris, acquis: s.jours_acquis, annee: s.annee })}</p>
          </Carte>
        ))}
        {(soldes.length === 0 || !profil.eligible_conge_annuel) && (
          <Alerte type="info">
            {profil.date_embauche === null
              ? t('Votre date d’entrée à l’usine n’est pas renseignée : aucun solde de congé annuel n’est disponible. Contactez l’administrateur.')
              : !profil.eligible_conge_annuel
                ? t('Vous avez moins d’un an d’ancienneté : vous n’avez pas encore de solde de congé annuel. Il vous sera attribué (18 jours par an, 21 jours si votre dernier enfant a 6 ans ou moins) à votre premier anniversaire dans l’entreprise.')
                : t('Aucun solde initialisé pour cette année.')}
          </Alerte>
        )}
      </div>

      {avecDemandes && <Carte
        titre={t('Mes dernières demandes')}
        action={<Link className="bouton bouton--primaire" to="/mes-demandes">{t('Voir tout / Nouvelle demande')}</Link>}
      >
        {demandes === null ? (
          <Chargement />
        ) : demandes.length === 0 ? (
          <p className="texte-discret">{t('Aucune demande pour le moment.')}</p>
        ) : (
          <TableDemandesResume demandes={demandes} />
        )}
      </Carte>}
    </>
  )
}

function TableauAdministrateur() {
  const { t } = useI18n()
  const [comptes, setComptes] = useState(null)
  const [departements, setDepartements] = useState(null)

  useEffect(() => {
    api.get('/utilisateurs/').then(({ data }) => setComptes(data.count))
    api.get('/departements/').then(({ data }) => setDepartements(data.count))
  }, [])

  return (
    <div className="grille-cartes">
      <Carte titre={t('Comptes utilisateurs')}>
        <p className="chiffre-cle">{comptes ?? '…'}</p>
        <Link className="bouton bouton--primaire" to="/admin/utilisateurs">{t('Gérer les comptes')}</Link>
      </Carte>
      <Carte titre={t('Départements')}>
        <p className="chiffre-cle">{departements ?? '…'}</p>
        <Link className="bouton bouton--primaire" to="/admin/departements">{t('Gérer les départements')}</Link>
      </Carte>
      <Carte titre={t('Paramètres système')}>
        <Link className="bouton bouton--primaire" to="/admin/parametres">{t('Valeurs par défaut')}</Link>
      </Carte>
      <Carte titre={t('Types de congés')}>
        <Link className="bouton bouton--primaire" to="/admin/types-conge">{t('Délai minimum et seuil par type')}</Link>
      </Carte>
    </div>
  )
}

export default function DashboardPage() {
  const { t } = useI18n()
  const { profil } = useAuth()

  return (
    <div className="page">
      <h1>{t('Salut {nom} 👋', { nom: profil.first_name })}</h1>
      {ROLES_AVEC_CONGES.includes(profil.role) && <TableauEmploye avecDemandes={profil.role === 'EMPLOYE'} />}
      {profil.role === 'ADMINISTRATEUR' && <TableauAdministrateur />}
    </div>
  )
}
