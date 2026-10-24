import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { listerTout, messageErreur } from '../api/client'
import Carte from '../components/Carte'
import Alerte from '../components/Alerte'
import Chargement from '../components/Chargement'

const texte = (v) => (v === null || v === undefined ? '' : String(v))
const enNombre = (v) => (v === '' ? null : Number(v))

/**
 * L'Administrateur règle, pour chaque type de congé défini par la RH, le délai
 * minimum de soumission et le seuil d'alerte de solde faible. Un champ laissé
 * vide signifie « utiliser le paramètre système par défaut ».
 */
export default function SeuilsTypesCongePage() {
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

  const modifie = (t) => {
    const s = saisies[t.id]
    return s && (s.delai !== texte(t.delai_minimum_jours) || s.seuil !== texte(t.seuil_alerte_jours))
  }

  function saisir(id, champ, valeur) {
    setSucces('')
    setSaisies({ ...saisies, [id]: { ...saisies[id], [champ]: valeur } })
  }

  async function enregistrer(t) {
    setErreur('')
    setSucces('')
    try {
      const { data } = await api.patch(`/types-conge/${t.id}/`, {
        delai_minimum_jours: enNombre(saisies[t.id].delai),
        seuil_alerte_jours: enNombre(saisies[t.id].seuil),
      })
      setTypes((liste) => liste.map((x) => (x.id === t.id ? data : x)))
      setSaisies((s) => ({ ...s, [t.id]: { delai: texte(data.delai_minimum_jours), seuil: texte(data.seuil_alerte_jours) } }))
      setSucces(`Seuils de « ${t.libelle} » enregistrés.`)
    } catch (err) {
      setErreur(messageErreur(err))
    }
  }

  if (types === null) return erreur ? <div className="page"><Alerte type="erreur">{erreur}</Alerte></div> : <Chargement />

  return (
    <div className="page">
      <h1>Délais et seuils par type de congé</h1>
      <Carte titre="Types définis par la RH">
        <p className="texte-discret">
          Pour chaque type de congé, fixez le <strong>délai minimum de soumission</strong> (jours entre la demande et
          le début du congé) et le <strong>seuil d’alerte</strong> de solde faible (jours restants, signalés à la RH).
          Un champ vide applique la valeur par défaut des{' '}
          <Link to="/admin/parametres">paramètres système</Link>
          {defauts && <> ({defauts.delai_minimum_jours} j de délai, {defauts.seuil_alerte_solde_jours} j de seuil)</>}.
          Les types eux-mêmes sont créés et modifiés par la RH.
        </p>
        <Alerte type="erreur">{erreur}</Alerte>
        <Alerte type="succes">{succes}</Alerte>
        <table className="tableau">
          <thead>
            <tr>
              <th>Type de congé</th><th>Décompté du solde</th>
              <th>Délai minimum (jours)</th><th>Seuil d’alerte (jours)</th><th></th>
            </tr>
          </thead>
          <tbody>
            {types.map((t) => (
              <tr key={t.id}>
                <td>{t.libelle}</td>
                <td>{t.decompte_solde ? 'Oui' : 'Non'}</td>
                <td>
                  <input
                    type="number" min="0" max="365" aria-label={`Délai minimum de ${t.libelle}`}
                    placeholder={defauts ? `défaut : ${defauts.delai_minimum_jours}` : ''}
                    value={saisies[t.id].delai} onChange={(e) => saisir(t.id, 'delai', e.target.value)}
                    style={{ width: 150 }}
                  />
                </td>
                <td>
                  <input
                    type="number" min="0" max="365" aria-label={`Seuil d’alerte de ${t.libelle}`}
                    placeholder={defauts ? `défaut : ${defauts.seuil_alerte_solde_jours}` : ''}
                    value={saisies[t.id].seuil} onChange={(e) => saisir(t.id, 'seuil', e.target.value)}
                    style={{ width: 150 }}
                  />
                </td>
                <td>
                  <button
                    className="bouton bouton--primaire" disabled={!modifie(t)}
                    aria-label={`Enregistrer ${t.libelle}`} onClick={() => enregistrer(t)}
                  >
                    Enregistrer
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
