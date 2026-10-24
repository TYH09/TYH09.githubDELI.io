import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Alerte from '../components/Alerte'

export default function LoginPage() {
  const { connecter, estConnecte, erreurConnexion } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [identifiant, setIdentifiant] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [enCours, setEnCours] = useState(false)

  if (estConnecte) {
    return <Navigate to={location.state?.depuis?.pathname || '/'} replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setEnCours(true)
    const ok = await connecter(identifiant, motDePasse)
    setEnCours(false)
    if (ok) navigate(location.state?.depuis?.pathname || '/', { replace: true })
  }

  return (
    <div className="page-connexion">
      <form className="carte carte--connexion" onSubmit={handleSubmit}>
        <div className="entete__marque entete__marque--centree">
          <span className="entete__logo">GC</span>
          <span>Gestionnaire de Congés</span>
        </div>
        <p className="texte-discret">Delifood Agro-Industry</p>
        <label>
          Identifiant
          <input type="text" value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} autoFocus required />
        </label>
        <label>
          Mot de passe
          <input type="password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} required />
        </label>
        <Alerte type="erreur">{erreurConnexion}</Alerte>
        <button className="bouton bouton--primaire" type="submit" disabled={enCours}>
          {enCours ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </div>
  )
}
