r"""
Cœur métier du Gestionnaire de Congés — correspond au diagramme de classes
de l'analyse conceptuelle UML (TypeConge, SoldeConge, DemandeConge,
Validation, Notification, JournalAudit, JourFerie), complété par un modèle
ParametresSysteme pour les seuils configurables (délai minimum, alertes —
cf. CDC §6.5 "En tant qu'administrateur, je veux configurer... les délais
minimums de soumission et les seuils d'alerte").

Workflow à DEUX niveaux (CDC v1.1 §2.2, §4.1, §5, §7) :
    BROUILLON -> EN_ATTENTE_MANAGER -> EN_ATTENTE_DIRECTION -> VALIDEE
                                   \-> REFUSEE            \-> REFUSEE
Un refus à n'importe quel niveau clôt immédiatement la demande.
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Paramétrage système (Administrateur)
# ---------------------------------------------------------------------------
class ParametresSysteme(models.Model):
    """Ligne singleton de paramètres ajustables par l'Administrateur."""

    delai_minimum_jours = models.PositiveIntegerField(
        default=settings.CONGES_DELAI_MINIMUM_JOURS_DEFAUT,
        help_text="Nombre de jours minimum entre la soumission et la date de début du congé.",
    )
    seuil_alerte_solde_jours = models.PositiveIntegerField(
        default=settings.CONGES_SEUIL_ALERTE_SOLDE_DEFAUT,
        help_text="En-dessous de ce seuil de jours restants, une alerte est levée pour la RH.",
    )

    class Meta:
        verbose_name = "Paramètres système"
        verbose_name_plural = "Paramètres système"

    def __str__(self):
        return "Paramètres système"

    @classmethod
    def actuels(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Jours fériés & fermetures (RH) — CDC §6.4
# ---------------------------------------------------------------------------
class JourFerie(models.Model):
    date = models.DateField(unique=True)
    libelle = models.CharField(max_length=150)
    recurrent = models.BooleanField(
        default=False, help_text="Si coché, le jour est considéré férié chaque année à la même date."
    )

    class Meta:
        verbose_name = "Jour férié / fermeture"
        verbose_name_plural = "Jours fériés / fermetures"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} — {self.libelle}"


DUREE_MATERNITE_JOURS = 90  # droit annuel : 3 mois, soit 90 jours calendaires (ouvrés + non ouvrés)
JOURS_PAR_MOIS_MATERNITE = 30  # 1 mois de congé de maternité = 30 jours calendaires décomptés
MOIS_MATERNITE_MAX = DUREE_MATERNITE_JOURS // JOURS_PAR_MOIS_MATERNITE  # 3


def mois_maternite_disponibles(jours_disponibles):
    """Durées (en mois) encore choisissables pour un congé de maternité, d'après
    les jours qu'il reste à l'employée : 3 mois de droit par an, à prendre en une
    ou plusieurs fois (1, 2 ou 3 mois à la fois). Ex. : après 1 mois pris -> [1, 2] ;
    après 2 mois -> [1] ; après 3 mois -> []."""
    return [m for m in range(1, MOIS_MATERNITE_MAX + 1) if m * JOURS_PAR_MOIS_MATERNITE <= jours_disponibles]


def date_de_retour(derniere_date_absence):
    """Premier jour de travail après un congé : le lendemain du dernier jour
    d'absence, en sautant week-ends et jours fériés (un jour férié récurrent
    tombe à la même date chaque année)."""
    feries = JourFerie.objects.filter(date__gte=derniere_date_absence)
    exacts = set(feries.values_list("date", flat=True))
    recurrents = set(
        (j.date.month, j.date.day) for j in JourFerie.objects.filter(recurrent=True)
    )
    jour = derniere_date_absence + timedelta(days=1)
    while jour.weekday() >= 5 or jour in exacts or (jour.month, jour.day) in recurrents:
        jour += timedelta(days=1)
    return jour


# ---------------------------------------------------------------------------
# Types de congés
# ---------------------------------------------------------------------------
class TypeConge(models.Model):
    libelle = models.CharField(max_length=100, unique=True)
    plafond_jours = models.PositiveIntegerField(
        null=True, blank=True, help_text="Laisser vide si le type de congé n'a pas de plafond annuel."
    )
    justificatif_obligatoire = models.BooleanField(default=False)
    regle_acquisition = models.CharField(
        max_length=255,
        default="annuelle",
        help_text="Description de la règle d'acquisition des droits (ex. 'mensuelle : 1.5 jour/mois').",
    )
    decompte_solde = models.BooleanField(
        default=True,
        help_text="Décoché pour les congés qui ne consomment pas de solde (ex. congé sans solde).",
    )
    reserve_a_sexe = models.CharField(
        max_length=1,
        choices=[("M", "Masculin"), ("F", "Féminin")],
        null=True,
        blank=True,
        help_text="Si renseigné, ce type n'est ouvert qu'aux utilisateurs de ce sexe "
                  "(ex. maternité : F, paternité : M). Vide = ouvert à tous.",
    )

    est_maternite = models.BooleanField(
        default=False,
        help_text="Congé de maternité : 3 mois (90 jours calendaires) par an, pris en 1, 2 ou 3 mois à la fois "
                  "dans la limite du solde restant ; la date de fin est calculée.",
    )
    delai_minimum_jours = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(365)],
        help_text="Délai minimum (en jours) entre la soumission et le début du congé, propre à ce type. "
                  "Vide = paramètre système par défaut. Configuré par l'Administrateur.",
    )
    seuil_alerte_jours = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(365)],
        help_text="En dessous de ce nombre de jours restants, une alerte est levée pour la RH, "
                  "pour ce type. Vide = paramètre système par défaut. Configuré par l'Administrateur.",
    )

    class Meta:
        verbose_name = "Type de congé"
        verbose_name_plural = "Types de congés"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle

    @property
    def est_annuel(self):
        """Congé décompté du solde annuel (hors maternité) : « Congé annuel »."""
        return self.decompte_solde and not self.est_maternite

    def delai_minimum_effectif(self):
        """Délai minimum applicable : celui du type, sinon le paramètre système."""
        if self.delai_minimum_jours is not None:
            return self.delai_minimum_jours
        return ParametresSysteme.actuels().delai_minimum_jours

    def seuil_alerte_effectif(self):
        """Seuil d'alerte applicable : celui du type, sinon le paramètre système."""
        if self.seuil_alerte_jours is not None:
            return self.seuil_alerte_jours
        return ParametresSysteme.actuels().seuil_alerte_solde_jours

    def est_ouvert_a(self, utilisateur):
        """Vrai si le sexe de l'utilisateur permet de prendre ce type de congé."""
        return not self.reserve_a_sexe or utilisateur.sexe == self.reserve_a_sexe

    def calculer_droits_acquis(self, utilisateur):
        """Équivalent de TypeConge.calculerDroitsAcquis(Utilisateur) du
        diagramme de classes. Implémentation simple (acquisition annuelle
        pleine) ; à affiner avec la RH selon la règle exacte retenue."""
        return float(self.plafond_jours or 0)


# ---------------------------------------------------------------------------
# Solde de congés (par utilisateur, par type, par année)
# ---------------------------------------------------------------------------
class SoldeConge(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="soldes"
    )
    type_conge = models.ForeignKey(TypeConge, on_delete=models.CASCADE, related_name="soldes")
    annee = models.PositiveIntegerField()
    jours_acquis = models.FloatField(default=0)
    jours_pris = models.FloatField(default=0)
    jours_restants = models.FloatField(default=0)

    class Meta:
        verbose_name = "Solde de congés"
        verbose_name_plural = "Soldes de congés"
        unique_together = ("utilisateur", "type_conge", "annee")
        ordering = ["-annee", "utilisateur"]

    def __str__(self):
        return f"{self.utilisateur} — {self.type_conge} {self.annee} : {self.jours_restants}j restants"

    def mettre_a_jour(self, delta):
        """Équivalent de SoldeConge.mettreAJour(delta) du diagramme de
        classes. delta > 0 crédite le solde, delta < 0 le débite (demande
        validée)."""
        self.jours_pris = self.jours_pris - delta if delta < 0 else self.jours_pris
        self.jours_restants = self.jours_restants + delta
        self.save(update_fields=["jours_pris", "jours_restants"])


# ---------------------------------------------------------------------------
# Demande de congé
# ---------------------------------------------------------------------------
class StatutDemande(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    EN_ATTENTE_MANAGER = "EN_ATTENTE_MANAGER", "En attente du chef de département"
    EN_ATTENTE_DIRECTION = "EN_ATTENTE_DIRECTION", "En attente de la Direction Générale"
    VALIDEE = "VALIDEE", "Validée"
    REFUSEE = "REFUSEE", "Refusée"
    ANNULEE = "ANNULEE", "Annulée"


class RegleMetierError(ValidationError):
    """Levée lorsqu'une demande enfreint une règle métier (solde, délai,
    chevauchement) — cf. DemandeConge.verifierReglesMetier() du diagramme de
    classes et CDC §7 "Vérification automatique des règles métier"."""


class DemandeConge(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="demandes"
    )
    type_conge = models.ForeignKey(TypeConge, on_delete=models.PROTECT, related_name="demandes")
    date_debut = models.DateField()
    date_fin = models.DateField()
    nb_jours_ouvres = models.FloatField(editable=False, default=0)
    nb_jours_decomptes = models.FloatField(
        editable=False, default=0,
        help_text="Jours débités du solde : les jours ouvrés, sauf pour la maternité (30 jours calendaires par mois).",
    )
    duree_maternite_mois = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(m, f"{m} mois") for m in range(1, MOIS_MATERNITE_MAX + 1)],
        help_text="Congé de maternité uniquement : durée choisie (1, 2 ou 3 mois de 30 jours).",
    )
    motif = models.CharField(max_length=255, blank=True)
    justificatif_fichier = models.FileField(upload_to="justificatifs/%Y/%m/", null=True, blank=True)
    statut = models.CharField(max_length=25, choices=StatutDemande.choices, default=StatutDemande.BROUILLON)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congés"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.utilisateur} — {self.type_conge} du {self.date_debut} au {self.date_fin} [{self.statut}]"

    # -- Règles métier --------------------------------------------------
    def calculer_jours_ouvres(self):
        """Équivalent de DemandeConge.calculerJoursOuvres() : exclut les
        week-ends et les jours fériés déclarés (CDC §14.1)."""
        if self.date_fin < self.date_debut:
            return 0
        feries = set(
            JourFerie.objects.filter(
                date__gte=self.date_debut, date__lte=self.date_fin
            ).values_list("date", flat=True)
        )
        jours = 0
        jour = self.date_debut
        while jour <= self.date_fin:
            if jour.weekday() < 5 and jour not in feries:  # 0=lundi ... 4=vendredi
                jours += 1
            jour += timedelta(days=1)
        return float(jours)

    def preparer_dates(self):
        """Congé de maternité : la date de fin n'est pas saisie, elle est
        calculée à partir de la date de départ et de la durée choisie
        (30 jours calendaires par mois)."""
        if self.type_conge.est_maternite and self.duree_maternite_mois:
            self.date_fin = self.date_debut + timedelta(days=self.duree_maternite_mois * JOURS_PAR_MOIS_MATERNITE - 1)

    def calculer_jours_decomptes(self):
        """Jours débités du solde : jours calendaires pour la maternité
        (combinaison de jours ouvrés et non ouvrés), sinon les jours ouvrés."""
        if self.type_conge.est_maternite:
            return float((self.duree_maternite_mois or 0) * JOURS_PAR_MOIS_MATERNITE)
        return self.calculer_jours_ouvres()

    @property
    def date_retour(self):
        """Premier jour de travail après le dernier jour d'absence."""
        return date_de_retour(self.date_fin)

    def verifier_regles_metier(self, utilisateur_cible=None):
        """Équivalent de DemandeConge.verifierReglesMetier() : lève une
        RegleMetierError si une règle n'est pas respectée, sinon ne retourne
        rien. Appelée à la soumission (CDC §7)."""
        utilisateur_cible = utilisateur_cible or self.utilisateur

        # Congés réservés à un sexe (maternité : F, paternité : M)
        if self.type_conge.reserve_a_sexe and not self.type_conge.est_ouvert_a(utilisateur_cible):
            if not utilisateur_cible.sexe:
                raise RegleMetierError(
                    f"Le sexe de l'employé n'est pas renseigné : impossible de vérifier "
                    f"l'accès au type « {self.type_conge} ». Contactez l'administrateur."
                )
            reserve = "aux femmes" if self.type_conge.reserve_a_sexe == "F" else "aux hommes"
            raise RegleMetierError(f"Le type de congé « {self.type_conge} » est réservé {reserve}.")

        if self.type_conge.est_maternite:
            if self.duree_maternite_mois not in range(1, MOIS_MATERNITE_MAX + 1):
                raise RegleMetierError("Choisissez la durée du congé de maternité : 1, 2 ou 3 mois.")
        elif self.duree_maternite_mois:
            raise RegleMetierError("La durée en mois ne concerne que le congé de maternité.")

        if self.date_debut < timezone.localdate():
            raise RegleMetierError("La date de début doit être aujourd'hui ou dans le futur.")
        if self.date_fin < self.date_debut:
            raise RegleMetierError("La date de fin doit être postérieure ou égale à la date de début.")

        delai = (self.date_debut - timezone.localdate()).days
        delai_requis = self.type_conge.delai_minimum_effectif()
        if delai < delai_requis:
            raise RegleMetierError(
                f"Le délai minimum de soumission est de {delai_requis} jour(s) "
                f"avant la date de début pour « {self.type_conge} »."
            )

        # Chevauchement avec une autre demande active du même employé
        chevauchement = DemandeConge.objects.filter(
            utilisateur=utilisateur_cible,
            statut__in=[
                StatutDemande.EN_ATTENTE_MANAGER,
                StatutDemande.EN_ATTENTE_DIRECTION,
                StatutDemande.VALIDEE,
            ],
            date_debut__lte=self.date_fin,
            date_fin__gte=self.date_debut,
        ).exclude(pk=self.pk)
        if chevauchement.exists():
            raise RegleMetierError("Cette période chevauche une autre demande déjà en cours ou validée.")

        # Congé de maternité : 3 mois par an au total, en 1, 2 ou 3 mois à la fois
        # (année du départ). Les demandes en attente et validées comptent déjà.
        if self.type_conge.est_maternite:
            engages = sum(
                d.nb_jours_decomptes for d in DemandeConge.objects.filter(
                    utilisateur=utilisateur_cible, type_conge=self.type_conge,
                    date_debut__year=self.date_debut.year,
                    statut__in=[
                        StatutDemande.EN_ATTENTE_MANAGER, StatutDemande.EN_ATTENTE_DIRECTION, StatutDemande.VALIDEE,
                    ],
                ).exclude(pk=self.pk)
            )
            restants = DUREE_MATERNITE_JOURS - engages
            disponibles = mois_maternite_disponibles(restants)
            if self.duree_maternite_mois not in disponibles:
                if not disponibles:
                    raise RegleMetierError(
                        f"Vous avez déjà pris ou demandé les 3 mois de congé de maternité pour {self.date_debut.year} : "
                        "il n'est plus disponible cette année."
                    )
                options = " ou ".join(f"{m} mois" for m in disponibles)
                raise RegleMetierError(
                    f"Il ne vous reste que {options} de congé de maternité pour {self.date_debut.year}."
                )

        # Solde suffisant (uniquement pour les types de congé décomptés du solde)
        if self.type_conge.decompte_solde:
            solde = SoldeConge.objects.filter(
                utilisateur=utilisateur_cible,
                type_conge=self.type_conge,
                annee=self.date_debut.year,
            ).first()
            jours_demandes = self.nb_jours_decomptes or self.calculer_jours_decomptes()
            if not solde and self.type_conge.est_maternite:
                raise RegleMetierError(f"Aucun solde « {self.type_conge} » n'est disponible pour {self.date_debut.year}.")
            if not solde:
                # Pas de solde = pas de congé annuel. On explique pourquoi.
                from accounts.models import ANCIENNETE_MIN_ANNEES

                if not utilisateur_cible.date_embauche:
                    raise RegleMetierError(
                        "Votre date d'entrée à l'usine n'est pas renseignée : aucun solde de congé annuel "
                        "n'est disponible. Contactez l'administrateur."
                    )
                if not utilisateur_cible.est_eligible_conge_annuel():
                    raise RegleMetierError(
                        f"Vous n'avez pas encore {ANCIENNETE_MIN_ANNEES} an d'ancienneté à l'usine : "
                        "vous ne disposez pas de solde de congé annuel pour le moment."
                    )
                raise RegleMetierError(f"Aucun solde « {self.type_conge} » n'est disponible pour {self.date_debut.year}.")
            if solde.jours_restants < jours_demandes:
                raise RegleMetierError("Solde de congés insuffisant pour cette période.")

        if self.type_conge.justificatif_obligatoire and not self.justificatif_fichier:
            raise RegleMetierError(f"Un justificatif est obligatoire pour le type « {self.type_conge} ».")

    def soumettre(self):
        """Équivalent de DemandeConge.soumettre() : calcule les jours
        ouvrés, applique les règles métier, puis fait passer la demande au
        1er niveau de validation (Manager)."""
        self.preparer_dates()
        self.nb_jours_ouvres = self.calculer_jours_ouvres()
        self.nb_jours_decomptes = self.calculer_jours_decomptes()
        self.verifier_regles_metier()
        self.statut = StatutDemande.EN_ATTENTE_MANAGER
        self.save()
        return self

    def annuler(self):
        """Équivalent de DemandeConge.annuler() — possible tant que la
        demande n'est pas déjà validée (CDC §6.1)."""
        if self.statut in (StatutDemande.VALIDEE, StatutDemande.REFUSEE, StatutDemande.ANNULEE):
            raise RegleMetierError("Seule une demande encore en cours de validation peut être annulée.")
        self.statut = StatutDemande.ANNULEE
        self.save(update_fields=["statut", "date_maj"])


# ---------------------------------------------------------------------------
# Validation (une occurrence par niveau effectivement franchi : 1 à 2 pour
# le circuit à deux niveaux)
# ---------------------------------------------------------------------------
class NiveauValidation(models.TextChoices):
    MANAGER = "MANAGER", "Chef de département"
    DIRECTION = "DIRECTION", "Direction Générale"


class DecisionValidation(models.TextChoices):
    APPROUVE = "APPROUVE", "Approuvé"
    REFUSE = "REFUSE", "Refusé"


class Validation(models.Model):
    demande = models.ForeignKey(DemandeConge, on_delete=models.CASCADE, related_name="validations")
    niveau = models.CharField(max_length=10, choices=NiveauValidation.choices)
    decision = models.CharField(max_length=10, choices=DecisionValidation.choices)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="validations_effectuees"
    )
    commentaire = models.CharField(max_length=255, blank=True)
    date_validation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Validation"
        verbose_name_plural = "Validations"
        ordering = ["date_validation"]

    def __str__(self):
        return f"{self.demande} — {self.get_niveau_display()} : {self.get_decision_display()}"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
class Notification(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    demande = models.ForeignKey(
        DemandeConge, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    message = models.CharField(max_length=255)
    canal = models.CharField(max_length=20, default="EMAIL")
    date_envoi = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.utilisateur} — {self.message[:50]}"


# ---------------------------------------------------------------------------
# Journal d'audit (entité autonome — cf. points clés de l'analyse UML)
# ---------------------------------------------------------------------------
class JournalAudit(models.Model):
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="actions_auditees"
    )
    action = models.CharField(max_length=100)
    entite_concernee = models.CharField(max_length=100)
    valeur_avant = models.TextField(blank=True)
    valeur_apres = models.TextField(blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrée du journal d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ["-date_action"]

    def __str__(self):
        return f"[{self.date_action:%Y-%m-%d %H:%M}] {self.auteur} — {self.action}"
