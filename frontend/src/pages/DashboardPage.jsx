import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import api from '../api/client'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'
import Alerte from '../components/Alerte'
import StatutBadge from '../components/StatutBadge'

function TableDemandesResume({ demandes }) {
  return (
    <table className="tableau">
      <thead>
        <tr><th>Type</th><th>Période</th><th>Jours décomptés</th><th>Statut</th></tr>
      </thead>
      <tbody>
        {demandes.map((d) => (
          <tr key={d.id}>
            <td>{d.type_conge_libelle}</td>
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
  const { soldes, profil } = useAuth()
  const [demandes, setDemandes] = useState(null)

  useEffect(() => {
    api.get('/demandes/').then(({ data }) => setDemandes(data.results.slice(0, 5)))
  }, [])

  return (
    <>
      <div className="grille-cartes">
        {soldes.map((s) => (
          <Carte key={s.id} titre={s.type_conge_libelle}>
            <p className="chiffre-cle">{s.jours_restants}<span> j. restants</span></p>
            <p className="texte-discret">{s.jours_pris} pris sur {s.jours_acquis} acquis ({s.annee})</p>
          </Carte>
        ))}
        {(soldes.length === 0 || !profil.eligible_conge_annuel) && (
          <Alerte type="info">
            {profil.date_embauche === null
              ? 'Votre date d’entrée à l’usine n’est pas renseignée : aucun solde de congé annuel n’est disponible. Contactez l’administrateur.'
              : !profil.eligible_conge_annuel
                ? 'Vous avez moins d’un an d’ancienneté : vous n’avez pas encore de solde de congé annuel. Il vous sera attribué (18 jours par an, 21 jours si votre dernier enfant a 6 ans ou moins) à votre premier anniversaire dans l’entreprise.'
                : 'Aucun solde initialisé pour cette année.'}
          </Alerte>
        )}
      </div>

      <Carte
        titre="Mes dernières demandes"
        action={<Link className="bouton bouton--primaire" to="/mes-demandes">Voir tout / Nouvelle demande</Link>}
      >
        {demandes === null ? (
          <Chargement />
        ) : demandes.length === 0 ? (
          <p className="texte-discret">Aucune demande pour le moment.</p>
        ) : (
          <TableDemandesResume demandes={demandes} />
        )}
      </Carte>
    </>
  )
}

function TableauValidateur({ niveau, lien }) {
  const [compte, setCompte] = useState(null)

  useEffect(() => {
    api.get('/demandes/', { params: { statut: niveau } }).then(({ data }) => setCompte(data.count))
  }, [niveau])

  return (
    <Carte titre="Demandes à valider">
      {compte === null ? (
        <Chargement />
      ) : (
        <>
          <p className="chiffre-cle">{compte}</p>
          <p className="texte-discret">en attente de votre décision</p>
          <Link className="bouton bouton--primaire" to={lien}>Traiter les demandes</Link>
        </>
      )}
    </Carte>
  )
}

function CarteAbsencesDuJour() {
  const [compte, setCompte] = useState(null)

  useEffect(() => {
    api.get('/equipe/absences/', { params: { periode: 'en_cours' } }).then(({ data }) => setCompte(data.count))
  }, [])

  return (
    <Carte titre="Absents aujourd’hui">
      {compte === null ? (
        <Chargement />
      ) : (
        <>
          <p className="chiffre-cle">{compte}</p>
          <p className="texte-discret">collaborateur(s) de votre département en congé</p>
          <Link className="bouton bouton--primaire" to="/absences">Voir les absences</Link>
        </>
      )}
    </Carte>
  )
}

function TableauRH() {
  const [indicateurs, setIndicateurs] = useState(null)

  useEffect(() => {
    api.get('/dashboard/rh/').then(({ data }) => setIndicateurs(data))
  }, [])

  if (!indicateurs) return <Chargement />

  return (
    <>
      <div className="grille-cartes">
        <Link className="carte-lien" to="/rh/demandes-en-attente">
          <Carte titre="Demandes en attente"><p className="chiffre-cle">{indicateurs.demandes_en_attente}</p></Carte>
        </Link>
        <Link className="carte-lien" to="/rh/employes-sans-conge-annuel">
          <Carte titre="Salariés sans congé annuel cette année"><p className="chiffre-cle">{indicateurs.salaries_sans_conge_annuel}</p></Carte>
        </Link>
        <Link className="carte-lien" to="/rh/alertes-solde">
          <Carte titre="Alertes solde faible"><p className="chiffre-cle">{indicateurs.alertes_solde_faible}</p></Carte>
        </Link>
      </div>
      <Link className="bouton bouton--primaire" to="/rh/dashboard">Voir le détail par département</Link>
    </>
  )
}

function TableauAdministrateur() {
  const [comptes, setComptes] = useState(null)
  const [departements, setDepartements] = useState(null)

  useEffect(() => {
    api.get('/utilisateurs/').then(({ data }) => setComptes(data.count))
    api.get('/departements/').then(({ data }) => setDepartements(data.count))
  }, [])

  return (
    <div className="grille-cartes">
      <Carte titre="Comptes utilisateurs">
        <p className="chiffre-cle">{comptes ?? '…'}</p>
        <Link className="bouton bouton--primaire" to="/admin/utilisateurs">Gérer les comptes</Link>
      </Carte>
      <Carte titre="Départements">
        <p className="chiffre-cle">{departements ?? '…'}</p>
        <Link className="bouton bouton--primaire" to="/admin/departements">Gérer les départements</Link>
      </Carte>
      <Carte titre="Paramètres système">
        <Link className="bouton bouton--primaire" to="/admin/parametres">Valeurs par défaut</Link>
      </Carte>
      <Carte titre="Types de congés">
        <Link className="bouton bouton--primaire" to="/admin/types-conge">Délai minimum et seuil par type</Link>
      </Carte>
    </div>
  )
}

export default function DashboardPage() {
  const { profil } = useAuth()

  return (
    <div className="page">
      <h1>Bonjour {profil.first_name} 👋</h1>
      {profil.role === 'EMPLOYE' && <TableauEmploye />}
      {profil.role === 'MANAGER' && (
        <div className="grille-cartes">
          <TableauValidateur niveau="EN_ATTENTE_MANAGER" lien="/validations/manager" />
          <CarteAbsencesDuJour />
        </div>
      )}
      {profil.role === 'DIRECTEUR' && <TableauValidateur niveau="EN_ATTENTE_DIRECTION" lien="/validations/direction" />}
      {profil.role === 'RH' && <TableauRH />}
      {profil.role === 'ADMINISTRATEUR' && <TableauAdministrateur />}
    </div>
  )
}
