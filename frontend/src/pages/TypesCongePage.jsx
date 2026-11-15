import { useEffect, useState } from 'react'
import api, { messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

const VIDE = {
  libelle: '', plafond_jours: '', justificatif_obligatoire: false,
  regle_acquisition: '', decompte_solde: true, reserve_a_sexe: '',
}

export default function TypesCongePage() {
  const { t } = useI18n()
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
    if (!window.confirm(t('Supprimer ce type de congé ?'))) return
    try {
      await api.delete(`/types-conge/${id}/`)
      charger()
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  return (
    <div className="page">
      <h1>{t('Types de congés')}</h1>

      <Carte titre={t('Ajouter un type de congé')}>
        <form className="formulaire" onSubmit={handleSubmit}>
          <div className="formulaire__ligne">
            <label>
              {t('Libellé')}
              <input type="text" required value={form.libelle} onChange={(e) => setForm({ ...form, libelle: e.target.value })} />
            </label>
            <label>
              {t('Plafond annuel (jours acquis par employé et par an ; obligatoire si décompté du solde)')}
              <input type="number" min="0" value={form.plafond_jours} onChange={(e) => setForm({ ...form, plafond_jours: e.target.value })} />
            </label>
          </div>
          <label>
            {t("Règle d'acquisition")}
            <input
              type="text" value={form.regle_acquisition}
              placeholder={t('ex. 1,5 jour / mois travaillé (défaut : annuelle)')}
              onChange={(e) => setForm({ ...form, regle_acquisition: e.target.value })}
            />
          </label>
          <label>
            {t('Réservé à un sexe')}
            <select value={form.reserve_a_sexe} onChange={(e) => setForm({ ...form, reserve_a_sexe: e.target.value })}>
              <option value="">{t('Ouvert à tous')}</option>
              <option value="F">{t('Femmes uniquement (ex. maternité)')}</option>
              <option value="M">{t('Hommes uniquement (ex. paternité)')}</option>
            </select>
          </label>
          <div className="formulaire__ligne">
            <label className="case-a-cocher">
              <input type="checkbox" checked={form.justificatif_obligatoire} onChange={(e) => setForm({ ...form, justificatif_obligatoire: e.target.checked })} />
              {t('Justificatif obligatoire')}
            </label>
            <label className="case-a-cocher">
              <input type="checkbox" checked={form.decompte_solde} onChange={(e) => setForm({ ...form, decompte_solde: e.target.checked })} />
              {t('Décompté du solde de congés')}
            </label>
          </div>
          <Alerte type="erreur">{erreur}</Alerte>
          <button className="bouton bouton--primaire" type="submit">{t('Ajouter')}</button>
        </form>
      </Carte>

      <Carte titre={t('Types existants')}>
        <p className="texte-discret">{t('Le délai minimum de soumission et le seuil d’alerte de chaque type sont réglés par l’Administrateur.')}</p>
        {types === null ? (
          <Chargement />
        ) : (
          <table className="tableau">
            <thead>
              <tr><th>{t('Libellé')}</th><th>{t('Plafond')}</th><th>{t('Justificatif')}</th><th>{t('Décompte solde')}</th><th>{t('Réservé à')}</th><th>{t('Délai minimum')}</th><th>{t('Seuil d’alerte')}</th><th>{t('Règle')}</th><th></th></tr>
            </thead>
            <tbody>
              {types.map((type) => (
                <tr key={type.id}>
                  <td>{t(type.libelle)}</td>
                  <td>{type.plafond_jours ?? '—'}</td>
                  <td>{type.justificatif_obligatoire ? t('Oui') : t('Non')}</td>
                  <td>{type.decompte_solde ? t('Oui') : t('Non')}</td>
                  <td>{type.reserve_a_sexe === 'F' ? t('Femmes') : type.reserve_a_sexe === 'M' ? t('Hommes') : t('Tous')}</td>
                  <td title={type.delai_minimum_jours === null ? t('Valeur par défaut des paramètres système') : t('Fixé par l’Administrateur')}>{t('{n} j', { n: type.delai_minimum_effectif })}</td>
                  <td title={type.seuil_alerte_jours === null ? t('Valeur par défaut des paramètres système') : t('Fixé par l’Administrateur')}>{t('{n} j', { n: type.seuil_alerte_effectif })}</td>
                  <td className="texte-discret">{type.regle_acquisition}</td>
                  <td><button className="bouton bouton--danger" onClick={() => supprimer(type.id)}>{t('Supprimer')}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Carte>
    </div>
  )
}
