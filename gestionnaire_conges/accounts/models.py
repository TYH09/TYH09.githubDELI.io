"""
Modèles du domaine "Identité & organisation" :
- Departement (regroupe des Utilisateurs, dirigé par un Utilisateur — cf. diagramme de classes)
- Utilisateur (remplace le modèle User par défaut de Django — un seul modèle
  porteur du RBAC, conformément au choix documenté dans l'analyse UML :
  "une seule classe Utilisateur porte l'attribut RoleUtilisateur plutôt
  qu'une hiérarchie d'héritage par type d'acteur").
"""
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models


# Droit au congé annuel : après ANCIENNETE_MIN_ANNEES année(s) révolue(s) à l'usine,
# l'employé dispose chaque année d'un solde de jours de congé annuel :
#   - JOURS_CONGE_ANNUEL_STANDARD (18) par défaut ;
#   - JOURS_CONGE_ANNUEL_MAJORE (21) pour une femme dont le dernier enfant a
#     AGE_MAX_ENFANT_MAJORATION ans ou moins (6 ans compris).
# La majoration ne s'applique que si la condition d'ancienneté est remplie.
ANCIENNETE_MIN_ANNEES = 1
JOURS_CONGE_ANNUEL_STANDARD = 18
JOURS_CONGE_ANNUEL_MAJORE = 21
AGE_MAX_ENFANT_MAJORATION = 6
AGE_MAX_ENFANT = 40  # borne de saisie (années)


class Departement(models.Model):
    nom = models.CharField(max_length=120, unique=True)
    responsable = models.OneToOneField(
        "accounts.Utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departement_dirige",
        help_text="Le chef de département (Manager) qui dirige ce département.",
    )
    directeur = models.ForeignKey(
        "accounts.Utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departements_supervises",
        help_text=(
            "Membre de la Direction Générale qui supervise ce département et valide ses "
            "demandes au 2e niveau. Un directeur peut superviser plusieurs départements. "
            "Sans directeur affecté, tout membre de la Direction peut traiter les demandes."
        ),
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def lister_employes(self):
        """Équivalent de Departement.listerEmployes() du diagramme de classes."""
        return self.employes.filter(actif=True)


class RoleUtilisateur(models.TextChoices):
    """Rôles RBAC — cf. CDC v1.1 §7 et §6.6 ("incluant désormais les rôles
    Directeur, chef de Département et RH")."""
    EMPLOYE = "EMPLOYE", "Employé"
    MANAGER = "MANAGER", "Manager / Chef de département"
    DIRECTEUR = "DIRECTEUR", "Direction Générale"
    RH = "RH", "Responsable RH"
    ADMINISTRATEUR = "ADMINISTRATEUR", "Administrateur système"


class FonctionDirection(models.TextChoices):
    """Fonctions couvertes par le rôle DIRECTEUR — cf. CDC v1.1 §5 :
    "Direction Générale (DQN, DU, DAF, DGA, DG)"."""
    DQN = "DQN", "Directeur Qualité & Normes"
    DU = "DU", "Directeur Usine"
    DAF = "DAF", "Directeur Administratif et Financier"
    DGA = "DGA", "Directeur Général Adjoint"
    DG = "DG", "Directeur Général"


class Sexe(models.TextChoices):
    """Sexe de l'utilisateur — sert aux règles des congés de maternité et de
    paternité (un congé réservé à un sexe n'est pas ouvert à l'autre)."""
    MASCULIN = "M", "Masculin"
    FEMININ = "F", "Féminin"


class Utilisateur(AbstractUser):
    """Un seul modèle Utilisateur pour tous les acteurs du système."""

    matricule = models.CharField(max_length=20, unique=True)
    sexe = models.CharField(
        max_length=1,
        choices=Sexe.choices,
        null=True,
        blank=True,
        help_text="Obligatoire à la création d'un compte (null uniquement pour les comptes antérieurs).",
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        validators=[RegexValidator(
            r"^(\+|\()?[0-9][0-9 .\-()]{5,18}[0-9]$",
            "Numéro de téléphone invalide (chiffres, espaces, +, - ou parenthèses ; 7 à 20 caractères).",
        )],
        help_text="Facultatif. Ex. : +237 6 70 12 34 56.",
    )
    role = models.CharField(max_length=20, choices=RoleUtilisateur.choices, default=RoleUtilisateur.EMPLOYE)
    fonction_direction = models.CharField(
        max_length=10,
        choices=FonctionDirection.choices,
        null=True,
        blank=True,
        help_text="Renseigné uniquement pour les utilisateurs de rôle Direction Générale.",
    )
    departement = models.ForeignKey(
        Departement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employes",
    )
    date_embauche = models.DateField(null=True, blank=True)
    a_enfant = models.BooleanField(
        null=True, blank=True,
        help_text="Employée uniquement : a-t-elle un enfant ? (Vide pour les autres comptes.)",
    )
    age_dernier_enfant = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(AGE_MAX_ENFANT)],
        help_text="Âge, en années, du dernier enfant (0 = moins d'un an). Renseigné si a_enfant.",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # -- Raccourcis de rôle, utilisés par les permissions DRF et l'admin -----
    @property
    def est_employe(self):
        return self.role == RoleUtilisateur.EMPLOYE

    @property
    def est_manager(self):
        return self.role == RoleUtilisateur.MANAGER

    @property
    def est_directeur(self):
        return self.role == RoleUtilisateur.DIRECTEUR

    @property
    def est_rh(self):
        return self.role == RoleUtilisateur.RH

    @property
    def est_administrateur(self):
        return self.role == RoleUtilisateur.ADMINISTRATEUR

    # -- Ancienneté & droit au congé annuel --------------------------------
    def anciennete_annees(self, a_date=None):
        """Nombre d'années révolues depuis la date d'entrée à l'usine
        (None si la date n'est pas renseignée)."""
        if not self.date_embauche:
            return None
        from django.utils import timezone

        a_date = a_date or timezone.localdate()
        d = self.date_embauche
        annees = a_date.year - d.year - ((a_date.month, a_date.day) < (d.month, d.day))
        return max(annees, 0)

    def est_eligible_conge_annuel(self, a_date=None):
        """Vrai si l'employé a au moins ANCIENNETE_MIN_ANNEES an(s) d'ancienneté."""
        annees = self.anciennete_annees(a_date)
        return annees is not None and annees >= ANCIENNETE_MIN_ANNEES

    @property
    def a_droit_majoration_enfant(self):
        """Femme dont le dernier enfant a 6 ans ou moins."""
        return bool(
            self.sexe == Sexe.FEMININ and self.a_enfant
            and self.age_dernier_enfant is not None
            and self.age_dernier_enfant <= AGE_MAX_ENFANT_MAJORATION
        )

    def droit_conge_annuel(self):
        """Nombre de jours de congé annuel par an : 21 (femme, dernier enfant de
        6 ans ou moins) sinon 18. Indépendant de l'ancienneté — l'éligibilité
        (≥ 1 an) est testée séparément par `est_eligible_conge_annuel`."""
        return JOURS_CONGE_ANNUEL_MAJORE if self.a_droit_majoration_enfant else JOURS_CONGE_ANNUEL_STANDARD

    def consulter_solde(self, type_conge, annee=None):
        """Équivalent de Utilisateur.consulterSolde() du diagramme de classes."""
        from django.utils import timezone
        from conges.models import SoldeConge

        annee = annee or timezone.now().year
        return SoldeConge.objects.filter(utilisateur=self, type_conge=type_conge, annee=annee).first()
