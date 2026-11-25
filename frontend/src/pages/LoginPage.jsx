import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Alerte from '../components/Alerte'
import ChampMotDePasse from '../components/ChampMotDePasse'
import LangueSwitch from '../components/LangueSwitch'
import { useI18n } from '../i18n/I18nContext'

export default function LoginPage() {
  const { t } = useI18n()
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
      <div className="page-connexion__langue"><LangueSwitch variante="clair" /></div>
      <form className="carte carte--connexion" onSubmit={handleSubmit}>
        <div className="entete__marque entete__marque--centree">
          <span className="entete__logo"><img src="/logo-belles-tomates.png" alt="Belles Tomates" /></span>
          <span>{t('Gestionnaire de Congés')}</span>
        </div>
        <p className="texte-discret">Delifood Agro-Industry</p>
        <label>
          {t('Identifiant')}
          <input type="text" value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} autoFocus required />
        </label>
        <label>
          {t('Mot de passe')}
          <ChampMotDePasse value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} required />
        </label>
        <Alerte type="erreur">{erreurConnexion}</Alerte>
        <button className="bouton bouton--primaire" type="submit" disabled={enCours}>
          {enCours ? t('Connexion…') : t('Se connecter')}
        </button>
      </form>
    </div>
  )
}
