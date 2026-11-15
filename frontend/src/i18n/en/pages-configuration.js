// Traductions anglaises — configuration (types de congé, seuils, jours fériés, paramètres) et App.
// Clé = texte français exact passé à t() ; {valeur} = valeur injectée ; {n:|s} = pluriel anglais.
export default {
  // App (titres de routes, démarrage)
  "Démarrage…": "Starting…",
  "Demandes à valider — Chef de département": "Requests to approve — Department head",
  "Demandes à valider — Direction Générale (décision finale)": "Requests to approve — General Management (final decision)",

  // Jours fériés
  "Supprimer ce jour férié ?": "Delete this public holiday?",
  "Jours fériés & fermetures": "Public holidays & closures",
  "Ajouter un jour férié / une fermeture": "Add a public holiday / closure",
  "Date": "Date",
  "Libellé": "Label",
  "Récurrent chaque année": "Recurs every year",
  "Ajouter": "Add",
  "Jours déclarés": "Declared days",
  "Récurrent": "Recurring",

  // Paramètres système
  "Paramètres enregistrés.": "Settings saved.",
  "Paramètres système": "System settings",
  "Seuils configurables": "Configurable thresholds",
  "Valeurs par défaut, appliquées aux types de congés qui n’ont pas leurs propres seuils (voir":
    "Default values, applied to leave types that have no thresholds of their own (see",
  "Délais et seuils par type": "Notice periods and thresholds by type",
  "Délai minimum de soumission (jours avant la date de début)": "Minimum submission notice (days before the start date)",
  "Seuil d'alerte solde faible (jours restants)": "Low balance alert threshold (days remaining)",
  "Enregistrer": "Save",

  // Seuils par type
  "Seuils de « {libelle} » enregistrés.": "Thresholds for “{libelle}” saved.",
  "Délais et seuils par type de congé": "Notice periods and thresholds by leave type",
  "Types définis par la RH": "Types defined by HR",
  "Pour chaque type de congé, fixez le": "For each leave type, set the",
  "délai minimum de soumission": "minimum submission notice",
  "(jours entre la demande et le début du congé) et le": "(days between the request and the start of the leave) and the",
  "seuil d’alerte": "alert threshold",
  "de solde faible (jours restants, signalés à la RH).": "for low balances (days remaining, reported to HR).",
  "Un champ vide applique la valeur par défaut des": "An empty field applies the default value from the",
  "paramètres système": "system settings",
  "{delai} j de délai, {seuil} j de seuil": "{delai} day{delai:|s} notice, {seuil} day{seuil:|s} threshold",
  "Les types eux-mêmes sont créés et modifiés par la RH.": "The types themselves are created and edited by HR.",
  "Type de congé": "Leave type",
  "Décompté du solde": "Deducted from balance",
  "Délai minimum (jours)": "Minimum notice (days)",
  "Seuil d’alerte (jours)": "Alert threshold (days)",
  "Délai minimum de {libelle}": "Minimum notice for {libelle}",
  "défaut : {n}": "default: {n}",
  "Seuil d’alerte de {libelle}": "Alert threshold for {libelle}",
  "Enregistrer {libelle}": "Save {libelle}",

  // Types de congé
  "Supprimer ce type de congé ?": "Delete this leave type?",
  "Types de congés": "Leave types",
  "Ajouter un type de congé": "Add a leave type",
  "Plafond annuel (jours acquis par employé et par an ; obligatoire si décompté du solde)":
    "Annual cap (days earned per employee per year; required if deducted from balance)",
  "Règle d'acquisition": "Accrual rule",
  "ex. 1,5 jour / mois travaillé (défaut : annuelle)": "e.g. 1.5 days / month worked (default: annual)",
  "Réservé à un sexe": "Restricted to one gender",
  "Ouvert à tous": "Open to everyone",
  "Femmes uniquement (ex. maternité)": "Women only (e.g. maternity)",
  "Hommes uniquement (ex. paternité)": "Men only (e.g. paternity)",
  "Justificatif obligatoire": "Supporting document required",
  "Décompté du solde de congés": "Deducted from leave balance",
  "Types existants": "Existing types",
  "Le délai minimum de soumission et le seuil d’alerte de chaque type sont réglés par l’Administrateur.":
    "The minimum submission notice and alert threshold of each type are set by the Administrator.",
  "Plafond": "Cap",
  "Justificatif": "Supporting document",
  "Décompte solde": "Balance deduction",
  "Réservé à": "Restricted to",
  "Délai minimum": "Minimum notice",
  "Seuil d’alerte": "Alert threshold",
  "Règle": "Rule",
  "Femmes": "Women",
  "Hommes": "Men",
  "Tous": "Everyone",
  "Valeur par défaut des paramètres système": "Default value from system settings",
  "Fixé par l’Administrateur": "Set by the Administrator",
  "{n} j": "{n} day{n:|s}",
}
