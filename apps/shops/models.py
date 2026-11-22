from django.conf import settings
from django.db import models


class Shop(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shop")
    name = models.JSONField()
    description = models.JSONField()
    logo_url = models.CharField(max_length=500, null=True, blank=True)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING, db_index=True)
    is_active = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(shipping_fee__gte=0), name="shops_shipping_fee_nonnegative"),
        ]
