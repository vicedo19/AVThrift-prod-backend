from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from inventory.models import StockReservation
from inventory.services import release_reservation


class Command(BaseCommand):
    help = "Release active stock reservations that have passed their expires_at timestamp."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = StockReservation.objects.filter(state=StockReservation.STATE_ACTIVE, expires_at__lt=now)
        count = 0
        # Ensure select_for_update runs inside a transaction
        with transaction.atomic():
            for res in qs.select_for_update(skip_locked=True):  # type: ignore[arg-type]
                release_reservation(reservation_id=res.id)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Expired reservations released: {count}"))
