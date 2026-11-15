import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { listerTout, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'
import { useI18n } from '../i18n/I18nContext'

const texte = (v) => (v === null || v === undefined ? '' : String(v))
const enNombre = (v) => (v === '' ? null : Number(v))

/**
 * L'Administrateur règle, pour chaque type de congé défini par la RH, le délai
 * minimum de soumission et le seuil d'alerte de solde faible. Un champ laissé
 * vide signifie « utiliser le paramètre système par défaut ».
 */
export default function SeuilsTypesCongePage() {
  const { t } = useI18n()
  const [types, setTypes] = useState(null)
  const [saisies, setSaisies] = useState({})   // id -> { delai, seuil } (texte saisi)
  const [defauts, setDefauts] = useState(null)
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')

  function initialiser(liste) {
    setTypes(liste)
    setSaisies(Object.fromEntries(liste.map((t) => [t.id, {
      delai: texte(t.delai_minimum_jours), seuil: texte(t.seuil_alerte_jours),
    }])))
  }

  useEffect(() => {
    let actif = true
    Promise.all([listerTout('/types-conge/'), api.get('/parametres-systeme/')])
      .then(([liste, { data }]) => {
        if (!actif) return
        initialiser(liste)
        setDefauts(data)
      })
      .catch((err) => actif && setErreur(messageErreur(err)))
    return () => { actif = false }
  }, [])

  const modifie = (type) => {
    const s = saisies[type.id]
    return s && (s.delai !== texte(type.delai_minimum_jours) || s.seuil !== texte(type.seuil_alerte_jours))
  }

  function saisir(id, champ, valeur) {
    setSucces('')
    setSaisies({ ...saisies, [id]: { ...saisies[id], [champ]: valeur } })
  }

  async function enregistrer(type) {
    setErreur('')
    setSucces('')
    try {
      const { data } = await api.patch(`/types-conge/${type.id}/`, {
        delai_minimum_jours: enNombre(saisies[type.id].delai),
        seuil_alerte_jours: enNombre(saisies[type.id].seuil),
      })
      setTypes((liste) => liste.map((x) => (x.id === type.id ? data : x)))
      setSaisies((s) => ({ ...s, [type.id]: { delai: texte(data.delai_minimum_jours), seuil: texte(data.seuil_alerte_jours) } }))
      setSucces(t('Seuils de « {libelle} » enregistrés.', { libelle: t(type.libelle) }))
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  if (types === null) return erreur ? <div className="page"><Alerte type="erreur">{erreur}</Alerte></div> : <Chargement />

  return (
    <div className="page">
      <h1>{t('Délais et seuils par type de congé')}</h1>
      <Carte titre={t('Types définis par la RH')}>
        <p className="texte-discret">
          {t('Pour chaque type de congé, fixez le')} <strong>{t('délai minimum de soumission')}</strong> {t('(jours entre la demande et le début du congé) et le')} <strong>{t('seuil d’alerte')}</strong> {t('de solde faible (jours restants, signalés à la RH).')}
          {' '}{t('Un champ vide applique la valeur par défaut des')}{' '}
          <Link to="/admin/parametres">{t('paramètres système')}</Link>
          {defauts && <> ({t('{delai} j de délai, {seuil} j de seuil', { delai: defauts.delai_minimum_jours, seuil: defauts.seuil_alerte_solde_jours })})</>}.
          {' '}{t('Les types eux-mêmes sont créés et modifiés par la RH.')}
        </p>
        <Alerte type="erreur">{erreur}</Alerte>
        <Alerte type="succes">{succes}</Alerte>
        <table className="tableau">
          <thead>
            <tr>
              <th>{t('Type de congé')}</th><th>{t('Décompté du solde')}</th>
              <th>{t('Délai minimum (jours)')}</th><th>{t('Seuil d’alerte (jours)')}</th><th></th>
            </tr>
          </thead>
          <tbody>
            {types.map((type) => (
              <tr key={type.id}>
                <td>{t(type.libelle)}</td>
                <td>{type.decompte_solde ? t('Oui') : t('Non')}</td>
                <td>
                  <input
                    type="number" min="0" max="365" aria-label={t('Délai minimum de {libelle}', { libelle: t(type.libelle) })}
                    placeholder={defauts ? t('défaut : {n}', { n: defauts.delai_minimum_jours }) : ''}
                    value={saisies[type.id].delai} onChange={(e) => saisir(type.id, 'delai', e.target.value)}
                    style={{ width: 150 }}
                  />
                </td>
                <td>
                  <input
                    type="number" min="0" max="365" aria-label={t('Seuil d’alerte de {libelle}', { libelle: t(type.libelle) })}
                    placeholder={defauts ? t('défaut : {n}', { n: defauts.seuil_alerte_solde_jours }) : ''}
                    value={saisies[type.id].seuil} onChange={(e) => saisir(type.id, 'seuil', e.target.value)}
                    style={{ width: 150 }}
                  />
                </td>
                <td>
                  <button
                    className="bouton bouton--primaire" disabled={!modifie(type)}
                    aria-label={t('Enregistrer {libelle}', { libelle: t(type.libelle) })} onClick={() => enregistrer(type)}
                  >
                    {t('Enregistrer')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Carte>
    </div>
  )
}
