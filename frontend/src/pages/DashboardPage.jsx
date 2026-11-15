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

function TableauEmploye() {
  const { t } = useI18n()
  const { soldes, profil } = useAuth()
  const [demandes, setDemandes] = useState(null)

  useEffect(() => {
    api.get('/demandes/', { params: { mes: 1 } }).then(({ data }) => setDemandes(data.results.slice(0, 5)))
  }, [])

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

      <Carte
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
      </Carte>
    </>
  )
}

function TableauValidateur({ niveau, lien, titre = 'Demandes à valider' }) {
  const { t } = useI18n()
  const [compte, setCompte] = useState(null)

  useEffect(() => {
    api.get('/demandes/', { params: { statut: niveau } }).then(({ data }) => setCompte(data.count))
  }, [niveau])

  return (
    <Carte titre={t(titre)}>
      {compte === null ? (
        <Chargement />
      ) : (
        <>
          <p className="chiffre-cle">{compte}</p>
          <p className="texte-discret">{t('en attente de votre décision')}</p>
          <Link className="bouton bouton--primaire" to={lien}>{t('Traiter les demandes')}</Link>
        </>
      )}
    </Carte>
  )
}

function CarteAbsencesDuJour() {
  const { t } = useI18n()
  const [compte, setCompte] = useState(null)

  useEffect(() => {
    api.get('/equipe/absences/', { params: { periode: 'en_cours' } }).then(({ data }) => setCompte(data.count))
  }, [])

  return (
    <Carte titre={t('Absents aujourd’hui')}>
      {compte === null ? (
        <Chargement />
      ) : (
        <>
          <p className="chiffre-cle">{compte}</p>
          <p className="texte-discret">{t('collaborateur(s) de votre département en congé')}</p>
          <Link className="bouton bouton--primaire" to="/absences">{t('Voir les absences')}</Link>
        </>
      )}
    </Carte>
  )
}

function TableauRH() {
  const { t } = useI18n()
  const [indicateurs, setIndicateurs] = useState(null)

  useEffect(() => {
    api.get('/dashboard/rh/').then(({ data }) => setIndicateurs(data))
  }, [])

  if (!indicateurs) return <Chargement />

  return (
    <>
      <div className="grille-cartes">
        <Link className="carte-lien" to="/rh/demandes-en-attente">
          <Carte titre={t('Demandes en attente')}><p className="chiffre-cle">{indicateurs.demandes_en_attente}</p></Carte>
        </Link>
        <Link className="carte-lien" to="/rh/employes-sans-conge-annuel">
          <Carte titre={t('Salariés sans congé annuel cette année')}><p className="chiffre-cle">{indicateurs.salaries_sans_conge_annuel}</p></Carte>
        </Link>
        <Link className="carte-lien" to="/rh/alertes-solde">
          <Carte titre={t('Alertes solde faible')}><p className="chiffre-cle">{indicateurs.alertes_solde_faible}</p></Carte>
        </Link>
      </div>
      <Link className="bouton bouton--primaire" to="/rh/dashboard">{t('Voir le détail par département')}</Link>
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
      {ROLES_AVEC_CONGES.includes(profil.role) && <TableauEmploye />}
      {profil.role === 'MANAGER' && (
        <div className="grille-cartes">
          <TableauValidateur niveau="EN_ATTENTE_MANAGER" lien="/validations/manager" />
          <CarteAbsencesDuJour />
        </div>
      )}
      {profil.role === 'DIRECTEUR' && <TableauValidateur niveau="EN_ATTENTE_DIRECTION" lien="/validations/direction" />}
      {profil.role === 'RH' && (
        <>
          <div className="grille-cartes">
            <TableauValidateur niveau="EN_ATTENTE_RH" lien="/validations/rh" titre="Demandes des directeurs à valider" />
          </div>
          <TableauRH />
        </>
      )}
      {profil.role === 'ADMINISTRATEUR' && <TableauAdministrateur />}
    </div>
  )
}
