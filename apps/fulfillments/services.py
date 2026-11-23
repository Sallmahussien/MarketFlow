from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.orders.models import Order

from .models import Fulfillment


NEXT_STATUS = {
    Fulfillment.Status.PENDING: Fulfillment.Status.PREPARING,
    Fulfillment.Status.PREPARING: Fulfillment.Status.SHIPPED,
    Fulfillment.Status.SHIPPED: Fulfillment.Status.DELIVERED,
}


def recalculate_order_status(order):
    statuses = set(order.fulfillments.exclude(status=Fulfillment.Status.CANCELED).values_list("status", flat=True))
    if statuses == {Fulfillment.Status.DELIVERED}:
        status = Order.Status.COMPLETED
    elif statuses & {Fulfillment.Status.SHIPPED, Fulfillment.Status.DELIVERED}:
        status = Order.Status.PARTIALLY_FULFILLED
    else:
        status = Order.Status.CONFIRMED
    if status != order.status:
        order.status = status
        order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def update_fulfillment(fulfillment, values):
    # Serialize updates by all sellers on the same order before recalculating its status.
    order = get_object_or_404(Order.objects.select_for_update(), pk=fulfillment.order_id)
    fulfillment = get_object_or_404(Fulfillment.objects.select_for_update(), pk=fulfillment.pk, shop=fulfillment.shop_id)
    if order.status not in Order.PAID_STATUSES:
        raise ValidationError("The order must be paid before updating its fulfillment.")

    status = values.get("status", fulfillment.status)
    if values.get("status") == Fulfillment.Status.CANCELED:
        raise ValidationError({"status": "Sellers cannot cancel a fulfillment."})
    if status != fulfillment.status and status != NEXT_STATUS.get(fulfillment.status):
        raise ValidationError({"status": "Advance to the next fulfillment status."})

    changes = {field: value for field, value in values.items() if getattr(fulfillment, field) != value}
    if changes and fulfillment.status in (Fulfillment.Status.DELIVERED, Fulfillment.Status.CANCELED):
        raise ValidationError("Tracking details are locked after delivery or cancellation.")
    if changes:
        for field, value in changes.items():
            setattr(fulfillment, field, value)
        fulfillment.save(update_fields=[*changes, "updated_at"])
        if "status" in changes:
            recalculate_order_status(order)
    return fulfillment
