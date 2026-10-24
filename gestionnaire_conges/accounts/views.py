from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from conges.droits import mettre_a_jour_droits, synchroniser_soldes
from conges.models import JournalAudit
from conges.permissions import EstAdministrateur, LectureSeuleOuRHAdmin, NestPasSimpleEmploye
from conges.serializers import SoldeCongeSerializer

from .models import Departement, RoleUtilisateur, Utilisateur
from .serializers import (
    ChangerMonMotDePasseSerializer, DefinirMotDePasseSerializer,
    DepartementSerializer, UtilisateurCreateSerializer, UtilisateurSerializer,
    UtilisateurUpdateSerializer,
)


class DepartementViewSet(viewsets.ModelViewSet):
    queryset = Departement.objects.select_related("responsable", "directeur").all()
    serializer_class = DepartementSerializer

    def get_permissions(self):
        # Lecture : tous ; création / modification : RH ou Administrateur ;
        # suppression : Administrateur uniquement.
        if self.action == "destroy":
            return [EstAdministrateur()]
        return [LectureSeuleOuRHAdmin()]

    def destroy(self, request, *args, **kwargs):
        """Suppression d'un département par l'Administrateur. Refusée tant
        que des utilisateurs (hors son chef) y sont rattachés : ils se
        retrouveraient sans département, donc sans chef pour valider leurs
        demandes. Le chef et le directeur superviseur sont simplement
        détachés."""
        departement = self.get_object()
        membres = departement.employes.exclude(pk=departement.responsable_id).count()
        if membres:
            return Response(
                {"detail": (
                    f"Impossible de supprimer « {departement.nom} » : {membres} utilisateur(s) y sont encore "
                    "rattachés. Réaffectez-les à un autre département avant de le supprimer."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        avant = {
            "nom": departement.nom,
            "responsable": getattr(departement.responsable, "username", None),
            "directeur": getattr(departement.directeur, "username", None),
        }
        pk = departement.pk
        departement.delete()
        JournalAudit.objects.create(
            auteur=request.user, action="Suppression département",
            entite_concernee=f"Departement#{pk}", valeur_avant=avant,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class UtilisateurViewSet(viewsets.ModelViewSet):
    """CRUD des comptes — création/modification/désactivation réservées à
    l'Administrateur (CDC §6.5). L'annuaire (liste/détail) est accessible à
    l'encadrement (Manager, Direction, RH, Administrateur) mais PAS à un
    simple Employé, qui consulte son propre profil via /api/me/."""

    queryset = (
        Utilisateur.objects.select_related("departement")
        .prefetch_related("departements_supervises")
        .order_by("last_name", "first_name")
    )
    filterset_fields = ["role", "departement", "actif", "sexe"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "definir_mot_de_passe"):
            return [EstAdministrateur()]
        return [NestPasSimpleEmploye()]

    def get_serializer_class(self):
        if self.action == "create":
            return UtilisateurCreateSerializer
        if self.action in ("update", "partial_update"):
            return UtilisateurUpdateSerializer
        return UtilisateurSerializer

    @staticmethod
    def _instantane(u):
        return {
            "username": u.username, "nom": u.get_full_name(), "email": u.email,
            "telephone": u.telephone, "date_embauche": str(u.date_embauche or ""),
            "a_enfant": u.a_enfant, "age_dernier_enfant": u.age_dernier_enfant, "matricule": u.matricule, "sexe": u.sexe, "role": u.role,
            "departement": getattr(u.departement, "nom", None), "actif": u.actif,
            "departements_supervises": sorted(d.nom for d in u.departements_supervises.all()),
        }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        mettre_a_jour_droits(user)  # solde de congé annuel si ≥ 1 an d'ancienneté
        JournalAudit.objects.create(
            auteur=request.user, action="Création utilisateur",
            entite_concernee=f"Utilisateur#{user.pk}", valeur_apres=self._instantane(user),
        )
        return Response(UtilisateurSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        avant = self._instantane(instance)
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop("partial", False))
        serializer.is_valid(raise_exception=True)
        mot_de_passe_change = bool(serializer.validated_data.get("password"))
        user = serializer.save()
        mettre_a_jour_droits(user)  # date d'entrée ou rôle modifiés : on réaligne les soldes
        user = self.get_queryset().get(pk=user.pk)  # relit les relations prefetch
        apres = self._instantane(user)
        if mot_de_passe_change:
            apres["mot_de_passe"] = "modifié"
        JournalAudit.objects.create(
            auteur=request.user, action="Modification utilisateur",
            entite_concernee=f"Utilisateur#{user.pk}", valeur_avant=avant, valeur_apres=apres,
        )
        return Response(UtilisateurSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """Suppression définitive d'un compte par l'Administrateur. Supprime
        aussi ses demandes, soldes et notifications (le journal d'audit est
        conservé, avec un instantané du compte). Garde-fous : on ne se
        supprime pas soi-même et on ne supprime pas le dernier administrateur
        actif. Pour conserver l'historique, préférer la désactivation."""
        utilisateur = self.get_object()
        if utilisateur.pk == request.user.pk:
            return Response({"detail": "Vous ne pouvez pas supprimer votre propre compte."},
                            status=status.HTTP_400_BAD_REQUEST)
        if (
            utilisateur.role == RoleUtilisateur.ADMINISTRATEUR
            and utilisateur.actif
            and not Utilisateur.objects.filter(role=RoleUtilisateur.ADMINISTRATEUR, actif=True)
            .exclude(pk=utilisateur.pk).exists()
        ):
            return Response({"detail": "Impossible : il doit toujours rester au moins un administrateur actif."},
                            status=status.HTTP_400_BAD_REQUEST)
        avant = self._instantane(utilisateur)
        avant["demandes_supprimees"] = utilisateur.demandes.count()
        pk = utilisateur.pk
        utilisateur.delete()
        JournalAudit.objects.create(
            auteur=request.user, action="Suppression utilisateur",
            entite_concernee=f"Utilisateur#{pk}", valeur_avant=avant,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="definir-mot-de-passe")
    def definir_mot_de_passe(self, request, pk=None):
        """Réinitialisation d'un mot de passe par l'Administrateur (ex. compte
        bloqué) — CDC §6.5."""
        utilisateur = self.get_object()
        serializer = DefinirMotDePasseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utilisateur.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        utilisateur.save(update_fields=["password"])
        JournalAudit.objects.create(
            auteur=request.user, action="Réinitialisation mot de passe",
            entite_concernee=f"Utilisateur#{utilisateur.pk}",
        )
        return Response({"detail": "Mot de passe mis à jour."})


class MeView(APIView):
    """Profil de l'utilisateur connecté + ses soldes de congés de l'année en
    cours (CDC §6.1 : "consulter mon solde de congés en temps réel")."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        synchroniser_soldes(user)  # idempotent : crée le solde annuel dû, ex. au 1er anniversaire
        soldes = user.soldes.filter(annee=timezone.now().year).select_related("type_conge")
        return Response({
            "profil": UtilisateurSerializer(user).data,
            "soldes": SoldeCongeSerializer(soldes, many=True).data,
        })


class ChangerMonMotDePasseView(APIView):
    """Tout utilisateur connecté peut changer son propre mot de passe."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangerMonMotDePasseSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Mot de passe mis à jour."}, status=status.HTTP_200_OK)
