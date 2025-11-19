from django.core.management.base import BaseCommand
from django.utils import timezone
from orders.models import IdempotencyKey


class Command(BaseCommand):
    help = "Delete expired idempotency key records based on expires_at"

    def handle(self, *args, **options):
        now = timezone.now()
        qs = IdempotencyKey.objects.filter(expires_at__lt=now)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired idempotency keys."))
