from django.db import models


class Fulfillment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        PREPARING = "PREPARING"
        SHIPPED = "SHIPPED"
        DELIVERED = "DELIVERED"
        CANCELED = "CANCELED"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="fulfillments")
    shop = models.ForeignKey("shops.Shop", on_delete=models.PROTECT, related_name="fulfillments")
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    tracking_number = models.CharField(max_length=150, null=True, blank=True)
    carrier_name = models.CharField(max_length=150, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "shop"], name="fulfillment_one_per_shop_order")]
