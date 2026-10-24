import { useState } from 'react'
import api from '../api/client'

/**
 * Ouvre le justificatif d'une demande. Le fichier n'a pas d'URL publique :
 * il est servi par l'API (GET /demandes/{id}/justificatif/) uniquement aux
 * personnes autorisées (employé, manager du département, direction
 * compétente, RH, admin). On le télécharge donc avec le jeton JWT puis on
 * l'ouvre dans un nouvel onglet.
 */
export default function Justificatif({ demande }) {
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  if (!demande.a_justificatif) {
    return <span className="texte-discret">Aucun justificatif</span>
  }

  async function ouvrir() {
    setEnCours(true)
    setErreur('')
    // L'onglet est ouvert tout de suite (pendant le clic, donc jamais bloqué
    // comme pop-up), puis on y charge le fichier une fois reçu.
    const fenetre = window.open('', '_blank')
    try {
      const reponse = await api.get(`/demandes/${demande.id}/justificatif/`, { responseType: 'blob' })
      const url = URL.createObjectURL(reponse.data)
      if (fenetre) {
        fenetre.opener = null
        fenetre.location.href = url
      } else {
        const lien = document.createElement('a')
        lien.href = url
        lien.download = demande.justificatif_nom || 'justificatif'
        lien.click()
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      if (fenetre) fenetre.close()
      setErreur('Impossible d’ouvrir le justificatif.')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <span>
      <button type="button" className="bouton bouton--discret" onClick={ouvrir} disabled={enCours}>
        {enCours ? '…' : '📎 Voir le justificatif'}
      </button>
      {erreur && <span className="alerte alerte--erreur">{erreur}</span>}
    </span>
  )
}
