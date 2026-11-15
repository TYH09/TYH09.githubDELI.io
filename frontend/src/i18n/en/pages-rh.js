// Traductions anglaises — espace RH, export, notifications, pages d'erreur.
// Clé = texte français exact passé à t() ; {valeur} = valeur injectée ; {n:|s} = pluriel anglais.
export default {
  // Pages d'erreur
  "403 — Accès refusé": "403 — Access denied",
  "Votre rôle ne permet pas d'accéder à cette page.": "Your role does not allow access to this page.",
  "404 — Page introuvable": "404 — Page not found",
  "Retour au tableau de bord": "Back to dashboard",

  // Notifications
  "Notifications": "Notifications",
  "Tout marquer comme lu": "Mark all as read",
  "Aucune notification.": "No notifications.",
  "Voir la demande →": "View request →",
  "Marquer comme lu": "Mark as read",

  // Export
  "Export des congés validés": "Export of approved leave",
  "Export CSV (Comptabilité)": "CSV export (Accounting)",
  "Le fichier ne contient que les demandes": "The file only contains",
  "validées": "approved",
  "(décision finale de la Direction) : employé, matricule, département, type de congé, période, jours ouvrés et date de validation. Les demandes en attente, refusées ou annulées n’y figurent pas.":
    "requests (final decision by General Management): employee, employee ID, department, leave type, period, working days and approval date. Pending, rejected or cancelled requests are not included.",
  "Le tri se fait sur la": "Sorting is based on the",
  "date de début": "start date",
  "du congé. Laissez l’année vide pour toutes les années.": "of the leave. Leave the year empty to include all years.",
  "Année": "Year",
  "Toutes": "All",
  "Mois": "Month",
  "Tous les mois": "All months",
  "Génération…": "Generating…",
  "Télécharger le CSV": "Download CSV",

  // Indicateurs RH
  "← Indicateurs RH": "← HR indicators",
  "Indicateurs RH — {annee}": "HR indicators — {annee}",
  "Demandes en attente (tous niveaux)": "Pending requests (all levels)",
  "Voir les demandes et leur niveau de validation →": "View requests and their approval level →",
  "Salariés sans congé annuel validé cette année": "Employees with no approved annual leave this year",
  "Voir la liste par département →": "View the list by department →",
  "Alertes solde faible": "Low balance alerts",
  "Voir les soldes concernés →": "View affected balances →",
  "Effectifs et congés par département": "Headcount and leave by department",
  "Tous les comptes actifs du département": "All active accounts in the department",
  "Effectif total": "Total headcount",
  "Comptes actifs de rôle Employé": "Active accounts with the Employee role",
  "dont employés": "of which employees",
  "Employés ayant au moins un an d'ancienneté : droit au congé annuel": "Employees with at least one year of service: entitled to annual leave",
  "Éligibles au congé annuel": "Eligible for annual leave",
  "Employés ayant au moins un congé validé dont le départ tombe dans l'année": "Employees with at least one approved leave starting this year",
  "Ont pris un congé": "Have taken leave",
  "Jours de congés validés": "Approved leave days",
  "Total": "Total",
  "Éligible : au moins un an d’ancienneté à la date du jour (18 jours de congé annuel par an, 21 pour une employée dont le dernier enfant a 6 ans ou moins).":
    "Eligible: at least one year of service as of today (18 days of annual leave per year, 21 for a female employee whose youngest child is 6 or under).",
  "« Ont pris un congé » : au moins un congé validé dont le départ tombe en {annee}.": "“Have taken leave”: at least one approved leave starting in {annee}.",

  // Demandes en attente (RH)
  "Niveaux de validation": "Approval levels",
  "1. Manager": "1. Manager",
  "2. Direction": "2. General Management",
  "— en attente": "— pending",
  "— à venir": "— upcoming",
  "Demandes en attente": "Pending requests",
  "Aucune demande à ce niveau.": "No requests at this level.",
  "Type": "Type",
  "Période": "Period",
  "Niveau de validation": "Approval level",
  "Statut": "Status",
  "Voir la demande": "View request",

  // Employés sans congé annuel
  "Sans département": "No department",
  "Employés éligibles sans congé annuel validé — {annee}": "Eligible employees with no approved annual leave — {annee}",
  "Employés ayant au moins un an d’ancienneté et aucun congé annuel validé cette année : {n}.":
    "Employees with at least one year of service and no approved annual leave this year: {n}.",
  "Tous les employés éligibles ont déjà pris un congé annuel.": "All eligible employees have already taken annual leave.",
  "Liste des employés": "Employee list",
  "Droit annuel": "Annual entitlement",
  "Jours restants": "Days remaining",
  "{n} j": "{n} day{n:|s}",

  // Alertes de solde faible
  "Alertes de solde faible — {annee}": "Low balance alerts — {annee}",
  "Soldes dont les jours restants sont inférieurs ou égaux au seuil d’alerte du type de congé : {n}.":
    "Balances whose remaining days are at or below the leave type's alert threshold: {n}.",
  "Aucun solde sous son seuil d’alerte.": "No balance below its alert threshold.",
  "Soldes concernés": "Affected balances",
  "Type de congé": "Leave type",
  "Jours acquis": "Days earned",
  "Seuil d’alerte": "Alert threshold",
}
