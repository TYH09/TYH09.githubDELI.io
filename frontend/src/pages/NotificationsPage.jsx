import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import Carte from '../components/Carte'
import Chargement from '../components/Chargement'

export default function NotificationsPage() {
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState(null)

  function charger() {
    api.get('/notifications/').then(({ data }) => setNotifications(data.results))
  }

  useEffect(charger, [])

  async function marquerLu(id) {
    await api.post(`/notifications/${id}/marquer_lu/`)
    charger()
  }

  async function toutMarquerLu() {
    await api.post('/notifications/tout-marquer-lu/')
    charger()
  }

  /** Un clic sur une notification la marque comme lue et ouvre la demande concernée. */
  async function ouvrir(n) {
    if (!n.lu) {
      try {
        await api.post(`/notifications/${n.id}/marquer_lu/`)
      } catch {
        /* la lecture n'est pas bloquante : on ouvre quand même la demande */
      }
    }
    if (n.demande) navigate(`/demandes/${n.demande}`)
    else charger()
  }

  return (
    <div className="page">
      <div className="page__entete">
        <h1>Notifications</h1>
        <button className="bouton bouton--discret" onClick={toutMarquerLu}>Tout marquer comme lu</button>
      </div>
      <Carte>
        {notifications === null ? (
          <Chargement />
        ) : notifications.length === 0 ? (
          <p className="texte-discret">Aucune notification.</p>
        ) : (
          <ul className="liste-notifications">
            {notifications.map((n) => (
              <li key={n.id} className={n.lu ? '' : 'liste-notifications__non-lue'}>
                <button type="button" className="notification__contenu" onClick={() => ouvrir(n)}>
                  <span className="notification__message">{n.message}</span>
                  <span className="texte-discret">
                    {new Date(n.date_envoi).toLocaleString('fr-FR')}
                    {n.demande && ' · Voir la demande →'}
                  </span>
                </button>
                {!n.lu && (
                  <button className="bouton bouton--discret" onClick={() => marquerLu(n.id)}>Marquer comme lu</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Carte>
    </div>
  )
}
