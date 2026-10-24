import os
from datetime import timedelta

from rest_framework import serializers

from accounts.serializers import UtilisateurSerializer

from .models import (
    JOURS_PAR_MOIS_MATERNITE, DemandeConge, JournalAudit, JourFerie, Notification,
    ParametresSysteme, SoldeConge, StatutDemande, TypeConge, Validation, mois_maternite_disponibles,
)


class TypeCongeSerializer(serializers.ModelSerializer):
    """Les deux seuils propres à chaque type (délai minimum, seuil d'alerte)
    sont configurés par l'Administrateur uniquement ; la RH définit le reste.
    Les valeurs *effectives* (propre au type, sinon paramètre système) sont
    exposées en lecture seule."""

    SEUILS = ("delai_minimum_jours", "seuil_alerte_jours")

    delai_minimum_effectif = serializers.SerializerMethodField()
    seuil_alerte_effectif = serializers.SerializerMethodField()

    class Meta:
        model = TypeConge
        fields = [
            "id", "libelle", "plafond_jours", "justificatif_obligatoire",
            "regle_acquisition", "decompte_solde", "reserve_a_sexe",
            "est_maternite", "delai_minimum_jours", "seuil_alerte_jours",
            "delai_minimum_effectif", "seuil_alerte_effectif",
        ]
        read_only_fields = ["est_maternite"]  # réglage de structure : migration / admin Django

    def get_delai_minimum_effectif(self, obj):
        return obj.delai_minimum_effectif()

    def get_seuil_alerte_effectif(self, obj):
        return obj.seuil_alerte_effectif()

    def validate(self, attrs):
        request = self.context.get("request")
        if request is not None and not request.user.est_administrateur:
            actuel = {c: getattr(self.instance, c, None) for c in self.SEUILS}
            # Renvoyer la valeur actuelle inchangée (PUT complet) reste permis.
            touches = [c for c in self.SEUILS if c in attrs and attrs[c] != actuel[c]]
            if touches:
                raise serializers.ValidationError(
                    {c: "Réservé à l'Administrateur (délai minimum et seuil d'alerte par type de congé)."
                     for c in touches}
                )
        return attrs


class JourFerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = JourFerie
        fields = ["id", "date", "libelle", "recurrent"]


class SoldeCongeSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source="utilisateur.get_full_name", read_only=True)
    type_conge_libelle = serializers.CharField(source="type_conge.libelle", read_only=True)
    est_maternite = serializers.BooleanField(source="type_conge.est_maternite", read_only=True)
    jours_engages = serializers.SerializerMethodField()
    jours_disponibles = serializers.SerializerMethodField()
    mois_disponibles = serializers.SerializerMethodField()

    class Meta:
        model = SoldeConge
        fields = [
            "id", "utilisateur", "utilisateur_nom", "type_conge", "type_conge_libelle", "est_maternite",
            "annee", "jours_acquis", "jours_pris", "jours_restants",
            "jours_engages", "jours_disponibles", "mois_disponibles",
        ]
        read_only_fields = ["jours_pris", "jours_restants"]

    def get_jours_engages(self, obj):
        """Jours de demandes encore en attente de validation (pas encore débités)."""
        return sum(
            d.nb_jours_decomptes for d in DemandeConge.objects.filter(
                utilisateur_id=obj.utilisateur_id, type_conge_id=obj.type_conge_id, date_debut__year=obj.annee,
                statut__in=[StatutDemande.EN_ATTENTE_MANAGER, StatutDemande.EN_ATTENTE_DIRECTION],
            )
        )

    def get_jours_disponibles(self, obj):
        return obj.jours_restants - self.get_jours_engages(obj)

    def get_mois_disponibles(self, obj):
        """Maternité : durées encore choisissables, en mois (ex. [1, 2], [1] ou [])."""
        if not obj.type_conge.est_maternite:
            return None
        return mois_maternite_disponibles(self.get_jours_disponibles(obj))


class ValidationSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.get_full_name", read_only=True)

    class Meta:
        model = Validation
        fields = ["id", "niveau", "decision", "auteur", "auteur_nom", "commentaire", "date_validation"]
        read_only_fields = fields


class DemandeCongeSerializer(serializers.ModelSerializer):
    """Lecture (liste / détail)."""

    utilisateur_detail = UtilisateurSerializer(source="utilisateur", read_only=True)
    type_conge_libelle = serializers.CharField(source="type_conge.libelle", read_only=True)
    validations = ValidationSerializer(many=True, read_only=True)
    statut_affiche = serializers.CharField(source="get_statut_display", read_only=True)
    # Le fichier n'est jamais exposé par une URL publique : il se télécharge
    # via l'endpoint authentifié /api/demandes/{id}/justificatif/.
    a_justificatif = serializers.SerializerMethodField()
    justificatif_nom = serializers.SerializerMethodField()
    justificatif_url = serializers.SerializerMethodField()
    est_maternite = serializers.BooleanField(source="type_conge.est_maternite", read_only=True)
    date_retour = serializers.DateField(read_only=True)

    class Meta:
        model = DemandeConge
        fields = [
            "id", "utilisateur", "utilisateur_detail", "type_conge", "type_conge_libelle",
            "est_maternite", "duree_maternite_mois",
            "date_debut", "date_fin", "date_retour", "nb_jours_ouvres", "nb_jours_decomptes", "motif",
            "a_justificatif", "justificatif_nom", "justificatif_url",
            "statut", "statut_affiche", "date_creation", "date_maj", "validations",
        ]
        read_only_fields = ["utilisateur", "nb_jours_ouvres", "nb_jours_decomptes", "statut", "date_creation", "date_maj"]


    def get_a_justificatif(self, obj):
        return bool(obj.justificatif_fichier)

    def get_justificatif_nom(self, obj):
        return os.path.basename(obj.justificatif_fichier.name) if obj.justificatif_fichier else None

    def get_justificatif_url(self, obj):
        return f"/api/demandes/{obj.pk}/justificatif/" if obj.justificatif_fichier else None


EXTENSIONS_JUSTIFICATIF = {
    # extension -> signatures de début de fichier acceptées
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}
TAILLE_MAX_JUSTIFICATIF = 5 * 1024 * 1024  # 5 Mo


class DemandeCongeCreateSerializer(serializers.ModelSerializer):
    """Écriture (soumission par l'employé) — l'utilisateur est déduit de la
    requête authentifiée, jamais fourni par le client."""

    class Meta:
        model = DemandeConge
        fields = ["id", "type_conge", "date_debut", "date_fin", "duree_maternite_mois", "motif", "justificatif_fichier"]
        extra_kwargs = {"date_fin": {"required": False}}

    def validate(self, attrs):
        """Congé de maternité : l'employée choisit la durée (1, 2 ou 3 mois) et sa
        date de départ, la date de fin est calculée (30 jours par mois). Autres
        types : la date de fin est obligatoire et aucune durée en mois n'est admise."""
        type_conge = attrs["type_conge"]
        if type_conge.est_maternite:
            mois = attrs.get("duree_maternite_mois")
            if not mois:
                raise serializers.ValidationError(
                    {"duree_maternite_mois": "Choisissez la durée du congé de maternité : 1, 2 ou 3 mois."}
                )
            attrs["date_fin"] = attrs["date_debut"] + timedelta(days=mois * JOURS_PAR_MOIS_MATERNITE - 1)
        else:
            if not attrs.get("date_fin"):
                raise serializers.ValidationError({"date_fin": "La date de fin est obligatoire."})
            if attrs.get("duree_maternite_mois"):
                raise serializers.ValidationError(
                    {"duree_maternite_mois": "La durée en mois ne concerne que le congé de maternité."}
                )
        return attrs

    def validate_justificatif_fichier(self, fichier):
        """PDF, PNG ou JPEG de 5 Mo maximum, dont le contenu correspond à
        l'extension : ces fichiers sont ouverts par le Manager et la Direction,
        on refuse donc tout ce qui pourrait s'exécuter (HTML, SVG, scripts…)."""
        if fichier is None:
            return fichier
        extension = os.path.splitext(fichier.name)[1].lstrip(".").lower()
        if extension not in EXTENSIONS_JUSTIFICATIF:
            raise serializers.ValidationError("Format refusé : joignez un PDF, un PNG ou un JPEG.")
        if fichier.size > TAILLE_MAX_JUSTIFICATIF:
            raise serializers.ValidationError("Fichier trop volumineux (5 Mo maximum).")
        debut = fichier.read(16)
        fichier.seek(0)
        if not any(debut.startswith(sig) for sig in EXTENSIONS_JUSTIFICATIF[extension]):
            raise serializers.ValidationError("Le contenu du fichier ne correspond pas à son extension.")
        return fichier


class DecisionValidationSerializer(serializers.Serializer):
    """Entrée des actions /valider-manager/ et /valider-direction/."""

    decision = serializers.ChoiceField(choices=["APPROUVE", "REFUSE"])
    commentaire = serializers.CharField(required=False, allow_blank=True, max_length=255)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "message", "canal", "date_envoi", "lu", "demande"]
        read_only_fields = ["id", "message", "canal", "date_envoi", "demande"]


class JournalAuditSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(source="auteur.get_full_name", read_only=True)

    class Meta:
        model = JournalAudit
        fields = ["id", "auteur", "auteur_nom", "action", "entite_concernee", "valeur_avant", "valeur_apres", "date_action"]
        read_only_fields = fields


class ParametresSystemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametresSysteme
        fields = ["delai_minimum_jours", "seuil_alerte_solde_jours"]
