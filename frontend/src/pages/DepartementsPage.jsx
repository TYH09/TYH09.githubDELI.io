import { useEffect, useState } from 'react'
import api, { listerTout, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

export default function DepartementsPage() {
  const { t } = useI18n()
  const [departements, setDepartements] = useState(null)
  const [managers, setManagers] = useState([])
  const [directeurs, setDirecteurs] = useState([])
  const [nom, setNom] = useState('')
  const [erreur, setErreur] = useState('')

  function charger() {
    listerTout('/departements/').then(setDepartements)
  }

  useEffect(() => {
    charger()
    listerTout('/utilisateurs/', { role: 'MANAGER', actif: true }).then(setManagers)
    listerTout('/utilisateurs/', { role: 'DIRECTEUR', actif: true }).then(setDirecteurs)
  }, [])

  async function creer(e) {
    e.preventDefault()
    setErreur('')
    try {
      await api.post('/departements/', { nom })
      setNom('')
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function modifier(id, champs) {
    setErreur('')
    try {
      await api.patch(`/departements/${id}/`, champs)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function supprimer(d) {
    if (!window.confirm(t('Supprimer le département « {nom} » ? Cette action est irréversible.', { nom: d.nom }))) return
    setErreur('')
    try {
      await api.delete(`/departements/${d.id}/`)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>{t('Départements')}</h1>
      <Alerte type="erreur">{erreur}</Alerte>

      <Carte titre={t('Créer un département')}>
        <form className="formulaire formulaire--ligne" onSubmit={creer}>
          <label>
            {t('Nom')}
            <input value={nom} onChange={(e) => setNom(e.target.value)} required />
          </label>
          <button className="bouton bouton--primaire" type="submit">{t('Créer')}</button>
        </form>
      </Carte>

      <Carte titre={t('Départements existants')}>
        {departements === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>{t('Nom')}</th><th>{t('Chef de département (1er niveau)')}</th><th>{t('Directeur superviseur (2e niveau)')}</th><th></th></tr>
            </thead>
            <tbody>
              {departements.map((d) => (
                <tr key={d.id}>
                  <td>{d.nom}</td>
                  <td>
                    <select value={d.responsable || ''} onChange={(e) => modifier(d.id, { responsable: e.target.value || null })}>
                      <option value="">{t('— Aucun —')}</option>
                      {managers.map((m) => (
                        <option key={m.id} value={m.id}>{m.first_name} {m.last_name}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      aria-label={t('Directeur de {nom}', { nom: d.nom })}
                      value={d.directeur || ''}
                      onChange={(e) => modifier(d.id, { directeur: e.target.value || null })}
                    >
                      <option value="">{t('— Toute la Direction —')}</option>
                      {directeurs.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.first_name} {m.last_name}{m.fonction_direction ? ` (${m.fonction_direction})` : ''}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button className="bouton bouton--danger" onClick={() => supprimer(d)}>{t('Supprimer')}</button>
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
