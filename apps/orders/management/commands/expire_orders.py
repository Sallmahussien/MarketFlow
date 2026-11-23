from time import sleep

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.reservations import expire_order


class Command(BaseCommand):
    help = "Release overdue checkout reservations. Use --watch to check every 15 seconds."

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        while True:
            due = Order.objects.filter(status=Order.Status.PENDING_PAYMENT, expires_at__lte=timezone.now())
            count = sum(expire_order(cart_id, pk) for cart_id, pk in
                        due.order_by("pk").values_list("cart_id", "pk").iterator())
            if count or not options["watch"]:
                self.stdout.write(f"Expired {count} orders.")
            if not options["watch"]:
                return
            close_old_connections()
            sleep(15)
