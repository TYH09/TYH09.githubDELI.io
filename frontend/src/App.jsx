import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import RequireAuth from './auth/RequireAuth'
import Layout from './components/Layout'
import Chargement from './components/Chargement'

import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import MesDemandesPage from './pages/MesDemandesPage'
import ValidationsEnAttentePage from './pages/ValidationsEnAttentePage'
import EquipePage from './pages/EquipePage'
import AbsencesEquipePage from './pages/AbsencesEquipePage'
import DemandeDetailPage from './pages/DemandeDetailPage'
import RHDashboardPage from './pages/RHDashboardPage'
import RHDemandesEnAttentePage from './pages/RHDemandesEnAttentePage'
import RHEmployesSansCongePage from './pages/RHEmployesSansCongePage'
import RHAlertesSoldePage from './pages/RHAlertesSoldePage'
import TypesCongePage from './pages/TypesCongePage'
import JoursFeriesPage from './pages/JoursFeriesPage'
import ExportPage from './pages/ExportPage'
import UtilisateursPage from './pages/UtilisateursPage'
import DepartementsPage from './pages/DepartementsPage'
import ParametresPage from './pages/ParametresPage'
import SeuilsTypesCongePage from './pages/SeuilsTypesCongePage'
import NotificationsPage from './pages/NotificationsPage'
import MonComptePage from './pages/MonComptePage'
import ForbiddenPage from './pages/ForbiddenPage'
import NotFoundPage from './pages/NotFoundPage'

/**
 * Arbre de routes. Chaque route métier est enveloppée dans
 * <RequireAuth roles={[...]}> : la liste de rôles reflète exactement les
 * permissions DRF correspondantes côté backend (défense en profondeur —
 * le vrai contrôle d'accès reste fait par l'API).
 */
function RoutesApplication() {
  const { chargementInitial } = useAuth()
  if (chargementInitial) return <Chargement libelle="Démarrage…" />

  return (
    <Routes>
      <Route path="/connexion" element={<LoginPage />} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/mon-compte" element={<MonComptePage />} />
        <Route path="/demandes/:id" element={<DemandeDetailPage />} />

        <Route path="/mes-demandes" element={<RequireAuth roles={['EMPLOYE']}><MesDemandesPage /></RequireAuth>} />

        <Route
          path="/validations/manager"
          element={
            <RequireAuth roles={['MANAGER']}>
              <ValidationsEnAttentePage
                niveau="EN_ATTENTE_MANAGER"
                actionPath="valider-manager"
                titre="Demandes à valider — Chef de département"
              />
            </RequireAuth>
          }
        />
        <Route
          path="/validations/direction"
          element={
            <RequireAuth roles={['DIRECTEUR']}>
              <ValidationsEnAttentePage
                niveau="EN_ATTENTE_DIRECTION"
                actionPath="valider-direction"
                titre="Demandes à valider — Direction Générale (décision finale)"
              />
            </RequireAuth>
          }
        />
        <Route path="/equipe" element={<RequireAuth roles={['MANAGER']}><EquipePage /></RequireAuth>} />
        <Route path="/absences" element={<RequireAuth roles={['MANAGER']}><AbsencesEquipePage /></RequireAuth>} />

        <Route path="/rh/dashboard" element={<RequireAuth roles={['RH']}><RHDashboardPage /></RequireAuth>} />
        <Route path="/rh/demandes-en-attente" element={<RequireAuth roles={['RH']}><RHDemandesEnAttentePage /></RequireAuth>} />
        <Route path="/rh/employes-sans-conge-annuel" element={<RequireAuth roles={['RH']}><RHEmployesSansCongePage /></RequireAuth>} />
        <Route path="/rh/alertes-solde" element={<RequireAuth roles={['RH']}><RHAlertesSoldePage /></RequireAuth>} />
        <Route path="/rh/types-conge" element={<RequireAuth roles={['RH']}><TypesCongePage /></RequireAuth>} />
        <Route path="/rh/jours-feries" element={<RequireAuth roles={['RH']}><JoursFeriesPage /></RequireAuth>} />
        <Route path="/rh/export" element={<RequireAuth roles={['RH']}><ExportPage /></RequireAuth>} />

        <Route path="/admin/utilisateurs" element={<RequireAuth roles={['ADMINISTRATEUR']}><UtilisateursPage /></RequireAuth>} />
        <Route path="/admin/departements" element={<RequireAuth roles={['ADMINISTRATEUR']}><DepartementsPage /></RequireAuth>} />
        <Route path="/admin/parametres" element={<RequireAuth roles={['ADMINISTRATEUR']}><ParametresPage /></RequireAuth>} />
        <Route path="/admin/types-conge" element={<RequireAuth roles={['ADMINISTRATEUR']}><SeuilsTypesCongePage /></RequireAuth>} />
      </Route>

      <Route path="/acces-refuse" element={<ForbiddenPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <RoutesApplication />
      </AuthProvider>
    </BrowserRouter>
  )
}
