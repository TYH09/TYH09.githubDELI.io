/**
 * Calculs de dates en « AAAA-MM-JJ » (sans fuseau : on travaille en UTC pour
 * éviter tout décalage d'un jour lié à l'heure d'été).
 */
const vers = (iso) => {
  const [a, m, j] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, j))
}
const iso = (d) => d.toISOString().slice(0, 10)

export function ajouterJours(dateIso, n) {
  const d = vers(dateIso)
  d.setUTCDate(d.getUTCDate() + n)
  return iso(d)
}

/**
 * Premier jour de travail après `derniereDateAbsence` : le lendemain, en sautant
 * week-ends et jours fériés (un férié « récurrent » tombe à la même date chaque année).
 * Même règle que le serveur (`date_de_retour`).
 */
export function dateDeRetour(derniereDateAbsence, feries = []) {
  const exacts = new Set(feries.map((f) => f.date))
  const recurrents = new Set(feries.filter((f) => f.recurrent).map((f) => f.date.slice(5)))
  let jour = ajouterJours(derniereDateAbsence, 1)
  for (let i = 0; i < 400; i += 1) {
    const jourSemaine = vers(jour).getUTCDay()
    if (jourSemaine !== 0 && jourSemaine !== 6 && !exacts.has(jour) && !recurrents.has(jour.slice(5))) break
    jour = ajouterJours(jour, 1)
  }
  return jour
}

export const versFr = (dateIso) => (dateIso ? dateIso.split('-').reverse().join('/') : '')
