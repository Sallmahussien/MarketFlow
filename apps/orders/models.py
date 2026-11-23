from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT"
        CONFIRMED = "CONFIRMED"
        EXPIRED = "EXPIRED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    cart = models.ForeignKey("carts.Cart", on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING_PAYMENT)
    address_snapshot = models.JSONField()
    shipping_by_shop = models.JSONField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_total = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="EGP")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart"], condition=models.Q(status="PENDING_PAYMENT"),
                                    name="orders_one_pending_per_cart"),
        ]
        indexes = [models.Index(fields=["status", "expires_at"])]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    shop = models.ForeignKey("shops.Shop", on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    fulfillment = models.ForeignKey("fulfillments.Fulfillment", on_delete=models.PROTECT,
                                    null=True, related_name="items")
