import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

const ANNEE_COURANTE = new Date().getFullYear()

export default function RHDashboardPage() {
  const { t } = useI18n()
  const annee = ANNEE_COURANTE
  const [indicateurs, setIndicateurs] = useState(null)

  useEffect(() => {
    api.get('/dashboard/rh/', { params: { annee } }).then(({ data }) => setIndicateurs(data))
  }, [annee])

  if (!indicateurs) return <Chargement />

  return (
    <div className="page">
      <h1>{t('Indicateurs RH — {annee}', { annee })}</h1>
      <div className="grille-cartes">
        <Link className="carte-lien" to="/rh/demandes-en-attente">
          <Carte titre={t('Demandes en attente (tous niveaux)')}>
            <p className="chiffre-cle">{indicateurs.demandes_en_attente}</p>
            <span className="carte-lien__voir">{t('Voir les demandes et leur niveau de validation →')}</span>
          </Carte>
        </Link>
        <Link className="carte-lien" to="/rh/employes-sans-conge-annuel">
          <Carte titre={t('Salariés sans congé annuel validé cette année')}>
            <p className="chiffre-cle">{indicateurs.salaries_sans_conge_annuel}</p>
            <span className="carte-lien__voir">{t('Voir la liste par département →')}</span>
          </Carte>
        </Link>
        <Link className="carte-lien" to="/rh/alertes-solde">
          <Carte titre={t('Alertes solde faible')}>
            <p className="chiffre-cle">{indicateurs.alertes_solde_faible}</p>
            <span className="carte-lien__voir">{t('Voir les soldes concernés →')}</span>
          </Carte>
        </Link>
      </div>

      <Carte titre={t('Effectifs et congés par département')}>
        <table className="tableau tableau--chiffres">
          <thead>
            <tr>
              <th>{t('Département')}</th>
              <th title={t('Tous les comptes actifs du département')}>{t('Effectif total')}</th>
              <th title={t('Comptes actifs de rôle Employé')}>{t('dont employés')}</th>
              <th title={t("Employés ayant au moins un an d'ancienneté : droit au congé annuel")}>{t('Éligibles au congé annuel')}</th>
              <th title={t("Employés ayant au moins un congé validé dont le départ tombe dans l'année")}>{t('Ont pris un congé')}</th>
              <th>{t('Jours de congés validés')}</th>
            </tr>
          </thead>
          <tbody>
            {indicateurs.par_departement.map((d) => (
              <tr key={d.departement}>
                <td>{d.departement}</td>
                <td>{d.effectif}</td>
                <td>{d.employes}</td>
                <td>{d.eligibles_conge_annuel}</td>
                <td>{d.ont_pris_conge}</td>
                <td>{d.jours_conges_valides}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th>{t('Total')}</th>
              <th>{indicateurs.totaux.effectif}</th>
              <th>{indicateurs.totaux.employes}</th>
              <th>{indicateurs.totaux.eligibles_conge_annuel}</th>
              <th>{indicateurs.totaux.ont_pris_conge}</th>
              <th>{indicateurs.totaux.jours_conges_valides}</th>
            </tr>
          </tfoot>
        </table>
        <p className="texte-discret">
          {t('Éligible : au moins un an d’ancienneté à la date du jour (18 jours de congé annuel par an, 21 pour une employée dont le dernier enfant a 6 ans ou moins).')}{' '}
          {t('« Ont pris un congé » : au moins un congé validé dont le départ tombe en {annee}.', { annee })}
        </p>
      </Carte>
    </div>
  )
}
