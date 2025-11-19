from datetime import timedelta

from cart.models import Cart
from cart.services import abandon_cart, abandon_cart_guest
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Abandon stale active carts by TTL, releasing reservations"

    def handle(self, *args, **options):
        from django.conf import settings

        ttl_minutes = getattr(settings, "CART_ABANDON_TTL_MINUTES", 120)
        cutoff = timezone.now() - timedelta(minutes=int(ttl_minutes))
        qs = Cart.objects.filter(status=Cart.STATUS_ACTIVE, updated_at__lt=cutoff)
        count = 0
        for cart in qs.iterator():
            if cart.user_id:
                abandon_cart(user=cart.user)
            elif cart.session_id:
                abandon_cart_guest(session_id=cart.session_id)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Abandoned {count} stale carts."))
