from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import Departement, RoleUtilisateur, Sexe, Utilisateur


class DepartementSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.CharField(source="responsable.get_full_name", read_only=True, default="")
    directeur_nom = serializers.CharField(source="directeur.get_full_name", read_only=True, default="")

    class Meta:
        model = Departement
        fields = ["id", "nom", "responsable", "responsable_nom", "directeur", "directeur_nom"]

    def validate_responsable(self, value):
        if value is not None and value.role != RoleUtilisateur.MANAGER:
            raise serializers.ValidationError("Le responsable d'un département doit avoir le rôle Manager.")
        return value

    def validate_directeur(self, value):
        if value is not None and value.role != RoleUtilisateur.DIRECTEUR:
            raise serializers.ValidationError(
                "Le directeur superviseur doit avoir le rôle Direction Générale."
            )
        return value


class UtilisateurSerializer(serializers.ModelSerializer):
    """Lecture d'un compte (annuaire, profil, détail de demande)."""

    departement_nom = serializers.CharField(source="departement.nom", read_only=True, default="")
    role_affiche = serializers.CharField(source="get_role_display", read_only=True)
    sexe_affiche = serializers.CharField(source="get_sexe_display", read_only=True, default="")
    departements_supervises = serializers.SerializerMethodField()
    anciennete_annees = serializers.SerializerMethodField()
    eligible_conge_annuel = serializers.SerializerMethodField()
    droit_conge_annuel = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "first_name", "last_name", "email", "telephone", "matricule",
            "sexe", "sexe_affiche", "role", "role_affiche", "fonction_direction",
            "departement", "departement_nom", "departements_supervises",
            "date_embauche", "anciennete_annees", "eligible_conge_annuel", "droit_conge_annuel",
            "a_enfant", "age_dernier_enfant", "actif", "is_active",
        ]
        read_only_fields = fields

    def get_anciennete_annees(self, obj):
        return obj.anciennete_annees()

    def get_eligible_conge_annuel(self, obj):
        return obj.est_eligible_conge_annuel()

    def get_droit_conge_annuel(self, obj):
        """Jours de congé annuel par an (18 ou 21), seulement pour un employé éligible."""
        if obj.role != RoleUtilisateur.EMPLOYE or not obj.est_eligible_conge_annuel():
            return None
        return obj.droit_conge_annuel()

    def get_departements_supervises(self, obj):
        if obj.role != RoleUtilisateur.DIRECTEUR:
            return []
        return [{"id": d.id, "nom": d.nom} for d in obj.departements_supervises.all()]


class _UtilisateurEcritureBase(serializers.ModelSerializer):
    """Règles communes à la création et à la modification d'un compte."""

    departements_supervises = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Departement.objects.all(), required=False,
        help_text="Départements supervisés (uniquement pour le rôle Direction Générale).",
    )

    def validate_telephone(self, value):
        return (value or "").strip()

    def validate_date_embauche(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("La date d'entrée à l'usine ne peut pas être dans le futur.")
        return value

    def validate(self, attrs):
        role = attrs.get("role", getattr(self.instance, "role", RoleUtilisateur.EMPLOYE))
        # Un employé doit avoir une date d'entrée à l'usine : elle fixe son
        # ancienneté, donc son droit au congé annuel. Exigée à la création et dès
        # qu'on touche au rôle ou à la date (les comptes anciens sans date ne
        # bloquent pas les modifications sans rapport).
        if role == RoleUtilisateur.EMPLOYE:
            date = attrs["date_embauche"] if "date_embauche" in attrs else getattr(self.instance, "date_embauche", None)
            if not date and (self.instance is None or "role" in attrs or "date_embauche" in attrs):
                raise serializers.ValidationError(
                    {"date_embauche": "La date d'entrée à l'usine est obligatoire pour un employé."}
                )
        self._valider_enfant(attrs, role)
        fonction = attrs.get("fonction_direction", getattr(self.instance, "fonction_direction", None))
        if role == RoleUtilisateur.DIRECTEUR:
            if not fonction:
                raise serializers.ValidationError(
                    {"fonction_direction": "La fonction de direction est obligatoire pour ce rôle."}
                )
        else:
            attrs["fonction_direction"] = None
            if attrs.get("departements_supervises"):
                raise serializers.ValidationError(
                    {"departements_supervises": "Seul un membre de la Direction Générale supervise des départements."}
                )
        return attrs

    def _valider_enfant(self, attrs, role):
        """Employée : indiquer si elle a un enfant et, si oui, l'âge du dernier
        (années). Ces informations fixent son droit (18 ou 21 jours de congé
        annuel). Exigées à la création et dès qu'on touche au rôle, au sexe ou à
        ces champs ; sans objet pour les autres comptes (valeurs effacées)."""
        sexe = attrs.get("sexe", getattr(self.instance, "sexe", None))
        if role != RoleUtilisateur.EMPLOYE or sexe != Sexe.FEMININ:
            attrs["a_enfant"] = None
            attrs["age_dernier_enfant"] = None
            return
        touche = any(c in attrs for c in ("a_enfant", "age_dernier_enfant", "role", "sexe"))
        a_enfant = attrs["a_enfant"] if "a_enfant" in attrs else getattr(self.instance, "a_enfant", None)
        if a_enfant is None:
            if self.instance is None or touche:
                raise serializers.ValidationError(
                    {"a_enfant": "Précisez si l'employée a un enfant (oui ou non)."}
                )
            return  # ancien compte non renseigné : une modification sans rapport reste possible
        if not a_enfant:
            attrs["a_enfant"] = False
            attrs["age_dernier_enfant"] = None
            return
        age = attrs["age_dernier_enfant"] if "age_dernier_enfant" in attrs else getattr(self.instance, "age_dernier_enfant", None)
        if age is None:
            raise serializers.ValidationError(
                {"age_dernier_enfant": "Indiquez l'âge du dernier enfant (en années, 0 s'il a moins d'un an)."}
            )
        attrs["a_enfant"] = True

    @staticmethod
    def _affecter_departements(utilisateur, departements):
        """Remplace l'ensemble des départements supervisés par `departements`
        (un département n'a qu'un directeur : il est réaffecté si besoin)."""
        ids = [d.id for d in departements]
        utilisateur.departements_supervises.exclude(id__in=ids).update(directeur=None)
        Departement.objects.filter(id__in=ids).update(directeur=utilisateur)


class UtilisateurCreateSerializer(_UtilisateurEcritureBase):
    """Réservé à l'Administrateur — CDC §6.5 "créer, modifier et désactiver
    des comptes utilisateurs"."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    sexe = serializers.ChoiceField(choices=Sexe.choices)  # obligatoire à la création

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "password", "first_name", "last_name", "email", "telephone", "matricule",
            "sexe", "role", "fonction_direction", "departement", "departements_supervises",
            "date_embauche", "a_enfant", "age_dernier_enfant",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        departements = validated_data.pop("departements_supervises", [])
        user = Utilisateur(**validated_data)
        user.set_password(password)
        user.save()
        self._affecter_departements(user, departements)
        return user


class UtilisateurUpdateSerializer(_UtilisateurEcritureBase):
    """Modification d'un compte par l'Administrateur : nom, prénom,
    identifiant, e-mail, matricule, sexe, rôle, département, statut et —
    optionnellement — nouveau mot de passe."""

    password = serializers.CharField(write_only=True, required=False, validators=[])

    class Meta:
        model = Utilisateur
        fields = [
            "id", "username", "password", "first_name", "last_name", "email", "telephone", "matricule",
            "sexe", "role", "fonction_direction", "departement", "departements_supervises",
            "date_embauche", "a_enfant", "age_dernier_enfant", "actif",
        ]
        extra_kwargs = {"sexe": {"allow_null": False, "required": False}}

    def validate_password(self, value):
        validate_password(value, self.instance)
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        if instance.role == RoleUtilisateur.ADMINISTRATEUR and instance.actif:
            perd_le_role = attrs.get("role", instance.role) != RoleUtilisateur.ADMINISTRATEUR
            desactive = attrs.get("actif", instance.actif) is False
            if (perd_le_role or desactive) and not Utilisateur.objects.filter(
                role=RoleUtilisateur.ADMINISTRATEUR, actif=True
            ).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError(
                    "Impossible : il doit toujours rester au moins un administrateur actif."
                )
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        departements = validated_data.pop("departements_supervises", None)
        ancien_role = instance.role

        for champ, valeur in validated_data.items():
            setattr(instance, champ, valeur)
        if "actif" in validated_data:
            instance.is_active = validated_data["actif"]
        if password:
            instance.set_password(password)
        instance.save()

        # Cohérence des rattachements quand le rôle change
        if ancien_role != instance.role:
            if ancien_role == RoleUtilisateur.MANAGER:
                Departement.objects.filter(responsable=instance).update(responsable=None)
            if ancien_role == RoleUtilisateur.DIRECTEUR:
                instance.departements_supervises.update(directeur=None)
        if departements is not None and instance.role == RoleUtilisateur.DIRECTEUR:
            self._affecter_departements(instance, departements)
        return instance


class ChangerMonMotDePasseSerializer(serializers.Serializer):
    """Changement de mot de passe par l'utilisateur lui-même."""

    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_ancien_mot_de_passe(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Ancien mot de passe incorrect.")
        return value


class DefinirMotDePasseSerializer(serializers.Serializer):
    """Réinitialisation du mot de passe d'un utilisateur par l'Administrateur."""

    nouveau_mot_de_passe = serializers.CharField(write_only=True, validators=[validate_password])
