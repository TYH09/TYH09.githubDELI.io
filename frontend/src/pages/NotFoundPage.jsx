import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="page page--erreur">
      <h1>404 — Page introuvable</h1>
      <Link className="bouton bouton--primaire" to="/">Retour au tableau de bord</Link>
    </div>
  )
}
