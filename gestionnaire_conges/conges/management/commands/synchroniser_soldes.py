from django.core.management.base import BaseCommand

from conges.droits import synchroniser_tous


class Command(BaseCommand):
    help = (
        "Crée les soldes annuels de congé annuel dus aux employés ayant au moins un an d'ancienneté "
        "(ex. ceux qui viennent de franchir leur premier anniversaire). Idempotent ; à planifier "
        "chaque nuit (cron)."
    )

    def handle(self, *args, **options):
        n = synchroniser_tous()
        self.stdout.write(self.style.SUCCESS(f"{n} solde(s) créé(s)."))
