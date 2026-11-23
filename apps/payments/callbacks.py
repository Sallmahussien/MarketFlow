from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.carts.models import Cart
from apps.fulfillments.models import Fulfillment
from apps.orders.models import Order
from apps.orders.reservations import expire_if_due

from .gateway import gateway
from .models import Payment, PaymentEvent


def receive_callback(body, signature):
    apply_event(gateway.verify_event(body, signature))


@transaction.atomic
def apply_event(event):
    try:
        payment = Payment.objects.select_related("order").get(provider=gateway.name, reference=event["reference"])
    except Payment.DoesNotExist as exc:
        raise ValidationError("Unknown payment reference.") from exc

    cart = Cart.objects.select_for_update().get(pk=payment.order.cart_id)
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if (event["order_reference"] != order.pk or event["amount"] != order.total_amount
            or event["currency"] != order.currency):
        raise ValidationError("Payment details do not match the order.")

    outcome = event["status"]
    receipt, created = PaymentEvent.objects.get_or_create(payment=payment, event_id=event["event_id"], defaults={
        "transaction_id": str(event["transaction_id"]), "outcome": outcome,
        "amount": event["amount"], "currency": event["currency"],
    })
    if not created:
        if receipt.outcome != outcome or receipt.transaction_id != str(event["transaction_id"]):
            raise ValidationError("Conflicting payment event.")
        return

    expire_if_due(order)
    # A success is terminal even when a stale failure arrives later.
    if payment.state == Payment.State.SUCCESS:
        return
    payment.transaction_id = str(event["transaction_id"])
    payment.state = outcome
    payment.save(update_fields=["state", "transaction_id", "updated_at"])
    if outcome == Payment.State.FAILED:
        return
    if order.status != Order.Status.PENDING_PAYMENT:
        receipt.attention_reason = "late_success" if order.status == Order.Status.EXPIRED else "additional_charge"
        receipt.save(update_fields=["attention_reason"])
        return
    order.payments.filter(state__in=(Payment.State.CREATING, Payment.State.OPEN)).update(
        state=Payment.State.EXPIRED, updated_at=timezone.now(),
    )
    for shop_id, fee in order.shipping_by_shop.items():
        fulfillment = Fulfillment.objects.create(order=order, shop_id=int(shop_id), shipping_fee=fee)
        order.items.filter(shop_id=int(shop_id)).update(fulfillment=fulfillment)
    order.status = Order.Status.CONFIRMED
    order.save(update_fields=["status", "updated_at"])
    cart.is_active = False
    cart.save(update_fields=["is_active", "updated_at"])
