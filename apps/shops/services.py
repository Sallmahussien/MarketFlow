from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Shop


def create_application(seller, values):
    shop, created = Shop.objects.get_or_create(user=seller, defaults=values)
    if not created:
        raise ValidationError({"detail": "This seller already has a shop."})
    return shop


@transaction.atomic
def update_own_shop(shop, values):
    shop = Shop.objects.select_for_update().get(pk=shop.pk)
    changes = {field: value for field, value in values.items() if value != getattr(shop, field)}
    if shop.status == Shop.Status.REJECTED and changes.keys() - {"is_active"}:
        changes.update(status=Shop.Status.PENDING, rejection_reason=None)
    if changes:
        for field, value in changes.items():
            setattr(shop, field, value)
        shop.save(update_fields=[*changes, "updated_at"])
    return shop


@transaction.atomic
def decide_application(shop, status, rejection_reason=None):
    shop = Shop.objects.select_for_update().get(pk=shop.pk)
    if shop.status != Shop.Status.PENDING:
        raise ValidationError({"status": "Only pending shop applications can be reviewed."})
    shop.status = status
    shop.rejection_reason = rejection_reason if status == Shop.Status.REJECTED else None
    shop.save(update_fields=["status", "rejection_reason", "updated_at"])
    return shop
