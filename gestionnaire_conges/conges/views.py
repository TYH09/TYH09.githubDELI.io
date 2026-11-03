import csv
import mimetypes
import os

from django.db.models import Q, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import RoleUtilisateur

from .models import (
    DemandeConge, JournalAudit, JourFerie, Notification,
    ParametresSysteme, RegleMetierError, SoldeConge, StatutDemande, TypeConge,
    date_de_retour,
)
from .permissions import EstDirecteur, EstManager, EstRHOuAdministrateur, LectureSeuleOuRHAdmin
from .serializers import (
    DecisionValidationSerializer, DemandeCongeCreateSerializer, DemandeCongeSerializer,
    JournalAuditSerializer, JourFerieSerializer, NotificationSerializer,
    ParametresSystemeSerializer, SoldeCongeSerializer, TypeCongeSerializer,
)
from .droits import propager_type_conge
from .services import WorkflowError, soumettre_demande, valider_niveau
from .models import NiveauValidation, DecisionValidation


class TypeCongeViewSet(viewsets.ModelViewSet):
    """Types de congés : définis par la RH ; l'Administrateur y configure le
    délai minimum de soumission et le seuil d'alerte propres à chaque type
    (champs refusés à la RH par le serializer)."""

    queryset = TypeConge.objects.all()
    serializer_class = TypeCongeSerializer
    permission_classes = [LectureSeuleOuRHAdmin]

    # Champs qui déterminent qui a droit à quel solde (et de combien).
    CHAMPS_DROIT = ("plafond_jours", "decompte_solde", "reserve_a_sexe")

    def perform_create(self, serializer):
        instance = serializer.save()
        propager_type_conge(instance)  # le solde de chaque employé apparaît avec le plafond défini

    def perform_update(self, serializer):
        avant = {c: getattr(serializer.instance, c) for c in TypeCongeSerializer.SEUILS}
        avant_droit = {c: getattr(serializer.instance, c) for c in self.CHAMPS_DROIT}
        instance = serializer.save()
        if any(getattr(instance, c) != v for c, v in avant_droit.items()):
            propager_type_conge(instance)  # un plafond modifié se répercute sur les soldes non entamés
        apres = {c: getattr(instance, c) for c in TypeCongeSerializer.SEUILS}
        if avant != apres:
            JournalAudit.objects.create(
                auteur=self.request.user,
                action="Seuils du type de congé modifiés",
                entite_concernee=f"TypeConge #{instance.pk} ({instance.libelle})",
                valeur_avant=str(avant),
                valeur_apres=str(apres),
            )


class JourFerieViewSet(viewsets.ModelViewSet):
    queryset = JourFerie.objects.all()
    serializer_class = JourFerieSerializer
    permission_classes = [LectureSeuleOuRHAdmin]


class SoldeCongeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SoldeCongeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["annee", "utilisateur", "type_conge"]

    def get_queryset(self):
        qs = SoldeConge.objects.select_related("utilisateur", "type_conge")
        user = self.request.user
        if user.est_rh or user.est_administrateur:
            return qs
        return qs.filter(utilisateur=user)


class DemandeCongeViewSet(viewsets.ModelViewSet):
    """Cœur du workflow : soumission (employé) et validation à deux niveaux
    (Manager puis Direction Générale)."""

    permission_classes = [IsAuthenticated]
    filterset_fields = ["statut", "type_conge", "utilisateur"]
    # Une demande n'est jamais modifiée ni supprimée par PUT/PATCH/DELETE :
    # seules la soumission, l'annulation et les décisions (actions POST) la
    # font évoluer, via la couche service.
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return DemandeCongeCreateSerializer
        return DemandeCongeSerializer

    def get_queryset(self):
        qs = DemandeConge.objects.select_related("utilisateur", "type_conge").prefetch_related("validations")
        user = self.request.user
        if user.est_employe:
            return qs.filter(utilisateur=user)
        if user.est_manager:
            # Le manager voit les demandes de son/ses département(s) dirigé(s)
            return qs.filter(utilisateur__departement__responsable=user)
        if user.est_directeur:
            # Périmètre : demandes des départements qu'il supervise, plus celles
            # des départements sans directeur affecté (et des employés sans
            # département) pour qu'aucune demande ne reste sans décideur.
            # Classées par département puis ancienneté (CDC §6.3).
            return qs.filter(
                Q(utilisateur__departement__directeur=user)
                | Q(utilisateur__departement__directeur__isnull=True)
            ).order_by("utilisateur__departement__nom", "date_creation")
        # RH / Administrateur : visibilité complète
        return qs

    def create(self, request, *args, **kwargs):
        if not request.user.est_employe:
            return Response(
                {"detail": "Seul un employé peut soumettre une demande de congé."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demande = DemandeConge(utilisateur=request.user, **serializer.validated_data)
        try:
            soumettre_demande(demande)
        except RegleMetierError as exc:
            return Response({"detail": exc.messages if hasattr(exc, "messages") else str(exc)},
                             status=status.HTTP_400_BAD_REQUEST)
        return Response(DemandeCongeSerializer(demande).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        demande = self.get_object()
        if demande.utilisateur != request.user and not (request.user.est_rh or request.user.est_administrateur):
            return Response({"detail": "Vous ne pouvez annuler que vos propres demandes."},
                             status=status.HTTP_403_FORBIDDEN)
        try:
            demande.annuler()
        except RegleMetierError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DemandeCongeSerializer(demande).data)

    @action(detail=True, methods=["get"], url_path="justificatif")
    def justificatif(self, request, pk=None):
        """Téléchargement authentifié du justificatif. `get_object()` applique
        le périmètre de lecture du rôle : l'employé concerné, le Manager du
        département, la Direction compétente, la RH et l'Administrateur
        l'ouvrent ; toute autre personne reçoit un 404."""
        demande = self.get_object()
        if not demande.justificatif_fichier:
            raise Http404("Aucun justificatif joint à cette demande.")
        nom = os.path.basename(demande.justificatif_fichier.name)
        extension = os.path.splitext(nom)[1].lstrip(".").lower()
        reponse = FileResponse(
            demande.justificatif_fichier.open("rb"),
            content_type=mimetypes.guess_type(nom)[0] or "application/octet-stream",
        )
        # Aperçu dans le navigateur uniquement pour les formats sûrs ; tout le
        # reste (fichiers antérieurs à la validation à l'envoi) est téléchargé.
        inline = extension in ("pdf", "png", "jpg", "jpeg")
        reponse["Content-Disposition"] = f'{"inline" if inline else "attachment"}; filename="{nom}"'
        reponse["X-Content-Type-Options"] = "nosniff"
        reponse["Cache-Control"] = "private, no-store"
        return reponse

    def _valider(self, request, pk, niveau):
        demande = self.get_object()
        entree = DecisionValidationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        try:
            demande = valider_niveau(
                demande,
                niveau=niveau,
                decision=entree.validated_data["decision"],
                auteur=request.user,
                commentaire=entree.validated_data.get("commentaire", ""),
            )
        except WorkflowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # La queryset de la vue applique prefetch_related("validations") : on
        # rafraîchit l'instance pour que la réponse inclue la Validation qui
        # vient d'être créée par ce même appel (sinon le cache prefetch,
        # peuplé avant l'écriture, resterait périmé).
        demande.refresh_from_db()
        return Response(DemandeCongeSerializer(demande).data)

    @action(detail=True, methods=["post"], url_path="valider-manager", permission_classes=[EstManager])
    def valider_manager(self, request, pk=None):
        """Fragment 2 du diagramme de séquence — validation 1er niveau."""
        demande = self.get_object()
        if demande.utilisateur.departement_id and demande.utilisateur.departement.responsable_id != request.user.id:
            return Response({"detail": "Vous ne gérez pas le département de cet employé."},
                             status=status.HTTP_403_FORBIDDEN)
        return self._valider(request, pk, NiveauValidation.MANAGER)

    @action(detail=True, methods=["post"], url_path="valider-direction", permission_classes=[EstDirecteur])
    def valider_direction(self, request, pk=None):
        """Fragment 3 du diagramme de séquence — validation finale (2e niveau)."""
        return self._valider(request, pk, NiveauValidation.DIRECTION)


class AbsencesEquipeView(APIView):
    """Liste des employés du (ou des) département(s) du Manager qui sont en
    congé ou le seront prochainement : nom, rôle, e-mail, téléphone, date de
    départ et date de retour. Ne concerne que les congés VALIDÉS.

    Le type de congé et le motif ne sont volontairement pas exposés (un
    congé maladie ou maternité relève de la vie privée).

    Paramètre `periode` : `en_cours` (en congé aujourd'hui), `a_venir`
    (départ futur) ; par défaut, les deux."""

    permission_classes = [EstManager]

    def get(self, request):
        periode = request.query_params.get("periode", "")
        if periode not in ("", "en_cours", "a_venir"):
            return Response({"detail": "Paramètre `periode` invalide (en_cours ou a_venir)."},
                            status=status.HTTP_400_BAD_REQUEST)
        aujourdhui = timezone.localdate()
        demandes = (
            DemandeConge.objects
            .filter(
                statut=StatutDemande.VALIDEE,
                utilisateur__departement__responsable=request.user,
                utilisateur__actif=True,
                date_fin__gte=aujourdhui,
            )
            .select_related("utilisateur", "utilisateur__departement")
            .order_by("date_debut", "utilisateur__last_name", "utilisateur__first_name")
        )
        if periode == "en_cours":
            demandes = demandes.filter(date_debut__lte=aujourdhui)
        elif periode == "a_venir":
            demandes = demandes.filter(date_debut__gt=aujourdhui)

        resultats = []
        for d in demandes:
            u = d.utilisateur
            resultats.append({
                "demande": d.pk,
                "utilisateur": u.pk,
                "prenom": u.first_name,
                "nom": u.last_name,
                "nom_complet": u.get_full_name(),
                "role": u.role,
                "role_affiche": u.get_role_display(),
                "email": u.email,
                "telephone": u.telephone,
                "departement": u.departement.nom if u.departement else "",
                "date_depart": d.date_debut,
                "date_fin": d.date_fin,
                "date_retour": date_de_retour(d.date_fin),
                "statut": "EN_COURS" if d.date_debut <= aujourdhui else "A_VENIR",
            })
        return Response({"count": len(resultats), "results": resultats})


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["lu"]

    def get_queryset(self):
        return Notification.objects.filter(utilisateur=self.request.user)

    @action(detail=True, methods=["post"])
    def marquer_lu(self, request, pk=None):
        notif = self.get_object()
        notif.lu = True
        notif.save(update_fields=["lu"])
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=["post"], url_path="tout-marquer-lu")
    def tout_marquer_lu(self, request):
        self.get_queryset().filter(lu=False).update(lu=True)
        return Response({"detail": "Notifications marquées comme lues."})


class JournalAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalAudit.objects.select_related("auteur").all()
    serializer_class = JournalAuditSerializer
    permission_classes = [EstRHOuAdministrateur]
    filterset_fields = ["action", "auteur"]


class ParametresSystemeView(APIView):
    """Paramétrage administrateur (CDC §6.5) : délai minimum de soumission,
    seuil d'alerte de solde."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        return Response(ParametresSystemeSerializer(ParametresSysteme.actuels()).data)

    def put(self, request):
        if not request.user.est_administrateur:
            return Response({"detail": "Réservé à l'Administrateur."}, status=status.HTTP_403_FORBIDDEN)
        params = ParametresSysteme.actuels()
        serializer = ParametresSystemeSerializer(params, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _annee_demandee(request):
    """Paramètre `annee` (année en cours par défaut) ; ValueError si invalide."""
    return int(request.query_params.get("annee", timezone.now().year))


def _reponse_annee_invalide():
    return Response({"detail": "Paramètre `annee` invalide."}, status=status.HTTP_400_BAD_REQUEST)


def _employes_sans_conge_annuel(annee):
    """Employés actifs ÉLIGIBLES au congé annuel (au moins un an d'ancienneté) qui
    n'ont aucun congé annuel validé dont le départ tombe dans `annee`."""
    from accounts.models import Utilisateur

    ont_pris = set(
        DemandeConge.objects.filter(
            statut=StatutDemande.VALIDEE, date_debut__year=annee,
            type_conge__decompte_solde=True, type_conge__est_maternite=False,
        ).values_list("utilisateur_id", flat=True)
    )
    employes = (
        Utilisateur.objects.filter(role=RoleUtilisateur.EMPLOYE, actif=True)
        .select_related("departement")
        .order_by("departement__nom", "last_name", "first_name")
    )
    return [u for u in employes if u.est_eligible_conge_annuel() and u.pk not in ont_pris]


def _soldes_faibles(annee):
    """Soldes de congé annuel (employés actifs) dont les jours restants sont
    au plus égaux au seuil d'alerte : celui du type de congé, sinon le seuil
    système par défaut. Le congé de maternité (90 j, une fois par an) n'est pas
    concerné."""
    params = ParametresSysteme.actuels()
    return (
        SoldeConge.objects.filter(
            annee=annee, type_conge__decompte_solde=True, type_conge__est_maternite=False,
            utilisateur__actif=True, utilisateur__role=RoleUtilisateur.EMPLOYE,
            jours_restants__lte=Coalesce("type_conge__seuil_alerte_jours", Value(params.seuil_alerte_solde_jours)),
        )
        .select_related("utilisateur", "utilisateur__departement", "type_conge")
        .order_by("jours_restants", "utilisateur__last_name", "utilisateur__first_name")
    )


class DashboardRHView(APIView):
    """Indicateurs clés pour la RH — CDC §2.2 / §6.4 / §11.4 ("Dashboard
    RH : soldes globaux, calendrier, demandes en attente, salariés sans
    congés, taux d'absentéisme par département").

    Chaque indicateur de tête a sa liste détaillée (voir les vues ci-dessous),
    de même effectif que le chiffre affiché.

    Par département : effectif total (tous les comptes actifs), nombre
    d'employés, nombre d'employés éligibles au congé annuel (au moins un an
    d'ancienneté aujourd'hui) et nombre d'employés ayant pris un congé (au
    moins un congé validé dont le départ tombe dans l'année)."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        try:
            annee = _annee_demandee(request)
        except ValueError:
            return _reponse_annee_invalide()

        demandes_en_attente = DemandeConge.objects.filter(
            statut__in=[StatutDemande.EN_ATTENTE_MANAGER, StatutDemande.EN_ATTENTE_DIRECTION]
        ).count()

        from accounts.models import Departement, Utilisateur

        validees_annee = DemandeConge.objects.filter(statut=StatutDemande.VALIDEE, date_debut__year=annee)
        ont_conge = set(validees_annee.values_list("utilisateur_id", flat=True))

        salaries_actifs = list(Utilisateur.objects.filter(role=RoleUtilisateur.EMPLOYE, actif=True))
        sans_conge_annuel = len(_employes_sans_conge_annuel(annee))
        soldes_faibles = _soldes_faibles(annee).count()

        actifs = list(Utilisateur.objects.filter(actif=True).values_list("pk", "departement_id", "role"))
        jours_par_dep = {}
        for d in validees_annee.select_related("utilisateur"):
            dep_id = d.utilisateur.departement_id
            jours_par_dep[dep_id] = jours_par_dep.get(dep_id, 0) + d.nb_jours_ouvres

        def ligne(libelle, dep_id):
            effectif = [pk for pk, dep, _ in actifs if dep == dep_id]
            employes = [u for u in salaries_actifs if u.departement_id == dep_id]
            return {
                "departement": libelle,
                "departement_id": dep_id,
                "effectif": len(effectif),
                "employes": len(employes),
                "eligibles_conge_annuel": sum(1 for u in employes if u.est_eligible_conge_annuel()),
                "ont_pris_conge": sum(1 for u in employes if u.pk in ont_conge),
                "jours_conges_valides": jours_par_dep.get(dep_id, 0),
            }

        par_departement = [ligne(dep.nom, dep.pk) for dep in Departement.objects.all()]
        if any(dep is None for _, dep, _ in actifs):  # comptes actifs sans département : on les compte aussi
            par_departement.append(ligne("Sans département", None))

        champs = ("effectif", "employes", "eligibles_conge_annuel", "ont_pris_conge", "jours_conges_valides")
        totaux = {c: sum(l[c] for l in par_departement) for c in champs}

        return Response({
            "annee": annee,
            "demandes_en_attente": demandes_en_attente,
            "salaries_sans_conge_annuel": sans_conge_annuel,
            "alertes_solde_faible": soldes_faibles,
            "par_departement": par_departement,
            "totaux": totaux,
        })


class DemandesEnAttenteRHView(APIView):
    """Liste des demandes en attente (tous niveaux) avec leur niveau de
    validation actuel et l'historique des décisions déjà prises."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        demandes = (
            DemandeConge.objects.filter(
                statut__in=[StatutDemande.EN_ATTENTE_MANAGER, StatutDemande.EN_ATTENTE_DIRECTION]
            )
            .select_related("utilisateur", "utilisateur__departement", "type_conge")
            .prefetch_related("validations", "validations__auteur")
            .order_by("date_creation")
        )
        donnees = DemandeCongeSerializer(demandes, many=True).data
        return Response({"count": len(donnees), "results": donnees})


class EmployesSansCongeAnnuelView(APIView):
    """Employés éligibles au congé annuel qui n'en ont pas encore pris (validé)
    cette année, avec leur département."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        try:
            annee = _annee_demandee(request)
        except ValueError:
            return _reponse_annee_invalide()
        employes = _employes_sans_conge_annuel(annee)
        soldes = {
            s.utilisateur_id: s.jours_restants
            for s in SoldeConge.objects.filter(
                annee=annee, utilisateur__in=employes, type_conge__decompte_solde=True,
                type_conge__est_maternite=False,
            )
        }
        resultats = [{
            "utilisateur": u.pk,
            "nom_complet": u.get_full_name(),
            "matricule": u.matricule,
            "departement": getattr(u.departement, "nom", None),
            "departement_id": u.departement_id,
            "anciennete_annees": u.anciennete_annees(),
            "droit_conge_annuel": u.droit_conge_annuel(),
            "jours_restants": soldes.get(u.pk),
        } for u in employes]
        return Response({"annee": annee, "count": len(resultats), "results": resultats})


class AlertesSoldeRHView(APIView):
    """Soldes faibles : employé, département, type de congé, jours restants et
    seuil d'alerte appliqué."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        try:
            annee = _annee_demandee(request)
        except ValueError:
            return _reponse_annee_invalide()
        resultats = [{
            "solde": s.pk,
            "utilisateur": s.utilisateur_id,
            "nom_complet": s.utilisateur.get_full_name(),
            "matricule": s.utilisateur.matricule,
            "departement": getattr(s.utilisateur.departement, "nom", None),
            "type_conge": s.type_conge.libelle,
            "jours_acquis": s.jours_acquis,
            "jours_restants": s.jours_restants,
            "seuil_alerte": s.type_conge.seuil_alerte_effectif(),
        } for s in _soldes_faibles(annee)]
        return Response({"annee": annee, "count": len(resultats), "results": resultats})


def _demandes_validees_pour_export(request):
    """Export : UNIQUEMENT les demandes définitivement validées (les demandes
    en attente, refusées ou annulées n'en font jamais partie)."""
    qs = (
        DemandeConge.objects.filter(statut=StatutDemande.VALIDEE)
        .select_related("utilisateur", "utilisateur__departement", "type_conge")
        .prefetch_related("validations")
        .order_by("date_debut", "utilisateur__last_name", "utilisateur__first_name")
    )
    annee = _entier_param(request, "annee", 1900, 2200)
    mois = _entier_param(request, "mois", 1, 12)
    if annee:
        qs = qs.filter(date_debut__year=annee)
    if mois:
        qs = qs.filter(date_debut__month=mois)  # tri par mois (avec ou sans année)
    return qs


def _entier_param(request, nom, minimum, maximum):
    """Lit un paramètre d'URL entier optionnel (vide = pas de filtre) ; 400 si invalide."""
    brut = (request.query_params.get(nom) or "").strip()
    if not brut:
        return None
    try:
        valeur = int(brut)
    except ValueError:
        valeur = None
    if valeur is None or not minimum <= valeur <= maximum:
        raise ValidationError({nom: f"Valeur invalide (attendu : entier entre {minimum} et {maximum})."})
    return valeur


EN_TETES_EXPORT = [
    "Employé", "Matricule", "Département", "Type de congé",
    "Date début", "Date fin", "Jours ouvrés", "Validée le", "Jours décomptés du solde",
]


def _lignes_export(qs):
    for d in qs:
        decision_finale = next(
            (v for v in reversed(list(d.validations.all())) if v.niveau == NiveauValidation.DIRECTION), None
        )
        yield [
            d.utilisateur.get_full_name(), d.utilisateur.matricule,
            getattr(d.utilisateur.departement, "nom", ""), d.type_conge.libelle,
            d.date_debut, d.date_fin, f"{d.nb_jours_ouvres:g}",  # 2.0 -> 2, 2.5 reste 2.5
            timezone.localtime(decision_finale.date_validation).date() if decision_finale else None,
            f"{d.nb_jours_decomptes:g}",  # maternité : 90 jours calendaires
        ]


class ExportDemandesCSVView(APIView):
    """Export CSV pour la Comptabilité (CDC §2.2 : "données fiables et
    exportables (CSV / Excel / PDF)") — demandes validées uniquement."""

    permission_classes = [EstRHOuAdministrateur]

    def get(self, request):
        qs = _demandes_validees_pour_export(request)  # valide aussi annee / mois (400 sinon)
        annee = request.query_params.get("annee", "").strip()
        mois = request.query_params.get("mois", "").strip()
        nom = "demandes_conges_validees"
        if annee:
            nom += f"_{annee}"
        if mois:
            nom += f"_{int(mois):02d}" if annee else f"_mois{int(mois):02d}"
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{nom}.csv"'
        response.write("\ufeff")  # BOM : Excel lit correctement les accents
        writer = csv.writer(response)
        writer.writerow(EN_TETES_EXPORT)
        for ligne in _lignes_export(qs):
            writer.writerow(ligne)
        return response
