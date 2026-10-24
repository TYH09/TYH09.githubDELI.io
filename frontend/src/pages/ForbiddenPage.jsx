import { Link } from 'react-router-dom'

export default function ForbiddenPage() {
  return (
    <div className="page page--erreur">
      <h1>403 — Accès refusé</h1>
      <p>Votre rôle ne permet pas d'accéder à cette page.</p>
      <Link className="bouton bouton--primaire" to="/">Retour au tableau de bord</Link>
    </div>
  )
}
