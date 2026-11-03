import { useEffect, useState } from 'react'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

const VIDE = {
  libelle: '', plafond_jours: '', justificatif_obligatoire: false,
  regle_acquisition: '', decompte_solde: true, reserve_a_sexe: '',
}

export default function TypesCongePage() {
  const [types, setTypes] = useState(null)
  const [form, setForm] = useState(VIDE)
  const [erreur, setErreur] = useState('')

  function charger() {
    api.get('/types-conge/').then(({ data }) => setTypes(data.results))
  }

  useEffect(charger, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setErreur('')
    try {
      // Si la règle d'acquisition est laissée vide, on ne l'envoie pas : l'API
      // applique alors sa valeur par défaut ("annuelle") au lieu de refuser une chaîne vide.
      const { regle_acquisition: regle, reserve_a_sexe: reserve, ...reste } = form
      await api.post('/types-conge/', {
        ...reste,
        reserve_a_sexe: reserve || null,
        plafond_jours: form.plafond_jours === '' ? null : Number(form.plafond_jours),
        ...(regle.trim() ? { regle_acquisition: regle.trim() } : {}),
      })
      setForm(VIDE)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  async function supprimer(id) {
    if (!window.confirm('Supprimer ce type de congé ?')) return
    try {
      await api.delete(`/types-conge/${id}/`)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>Types de congés</h1>

      <Carte titre="Ajouter un type de congé">
        <form className="formulaire" onSubmit={handleSubmit}>
          <div className="formulaire__ligne">
            <label>
              Libellé
              <input type="text" required value={form.libelle} onChange={(e) => setForm({ ...form, libelle: e.target.value })} />
            </label>
            <label>
              Plafond annuel (jours acquis par employé et par an ; obligatoire si décompté du solde)
              <input type="number" min="0" value={form.plafond_jours} onChange={(e) => setForm({ ...form, plafond_jours: e.target.value })} />
            </label>
          </div>
          <label>
            Règle d'acquisition
            <input
              type="text" value={form.regle_acquisition}
              placeholder="ex. 1,5 jour / mois travaillé (défaut : annuelle)"
              onChange={(e) => setForm({ ...form, regle_acquisition: e.target.value })}
            />
          </label>
          <label>
            Réservé à un sexe
            <select value={form.reserve_a_sexe} onChange={(e) => setForm({ ...form, reserve_a_sexe: e.target.value })}>
              <option value="">Ouvert à tous</option>
              <option value="F">Femmes uniquement (ex. maternité)</option>
              <option value="M">Hommes uniquement (ex. paternité)</option>
            </select>
          </label>
          <div className="formulaire__ligne">
            <label className="case-a-cocher">
              <input type="checkbox" checked={form.justificatif_obligatoire} onChange={(e) => setForm({ ...form, justificatif_obligatoire: e.target.checked })} />
              Justificatif obligatoire
            </label>
            <label className="case-a-cocher">
              <input type="checkbox" checked={form.decompte_solde} onChange={(e) => setForm({ ...form, decompte_solde: e.target.checked })} />
              Décompté du solde de congés
            </label>
          </div>
          <Alerte type="erreur">{erreur}</Alerte>
          <button className="bouton bouton--primaire" type="submit">Ajouter</button>
        </form>
      </Carte>

      <Carte titre="Types existants">
        <p className="texte-discret">Le délai minimum de soumission et le seuil d’alerte de chaque type sont réglés par l’Administrateur.</p>
        {types === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>Libellé</th><th>Plafond</th><th>Justificatif</th><th>Décompte solde</th><th>Réservé à</th><th>Délai minimum</th><th>Seuil d’alerte</th><th>Règle</th><th></th></tr>
            </thead>
            <tbody>
              {types.map((t) => (
                <tr key={t.id}>
                  <td>{t.libelle}</td>
                  <td>{t.plafond_jours ?? '—'}</td>
                  <td>{t.justificatif_obligatoire ? 'Oui' : 'Non'}</td>
                  <td>{t.decompte_solde ? 'Oui' : 'Non'}</td>
                  <td>{t.reserve_a_sexe === 'F' ? 'Femmes' : t.reserve_a_sexe === 'M' ? 'Hommes' : 'Tous'}</td>
                  <td title={t.delai_minimum_jours === null ? 'Valeur par défaut des paramètres système' : 'Fixé par l’Administrateur'}>{t.delai_minimum_effectif} j</td>
                  <td title={t.seuil_alerte_jours === null ? 'Valeur par défaut des paramètres système' : 'Fixé par l’Administrateur'}>{t.seuil_alerte_effectif} j</td>
                  <td className="texte-discret">{t.regle_acquisition}</td>
                  <td><button className="bouton bouton--danger" onClick={() => supprimer(t.id)}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
