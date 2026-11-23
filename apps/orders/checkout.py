from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts.models import Address
from apps.carts.models import Cart
from apps.payments.callbacks import apply_event
from apps.payments.gateway import GatewayUnavailable, gateway
from apps.payments.models import Payment

from .models import Order
from .reservations import expire_if_due, locked_customer_cart, reserve_order


PAYMENT_EXPIRY_MARGIN = timedelta(minutes=1)


def current_attempt(order):
    payment = order.payments.order_by("-pk").first()
    if payment and payment.state not in (Payment.State.FAILED, Payment.State.EXPIRED):
        return payment
    pay_by = order.expires_at - PAYMENT_EXPIRY_MARGIN
    if pay_by <= timezone.now():
        raise PermissionDenied("The payment window has closed for this order.")
    return Payment.objects.create(order=order, provider=gateway.name, expires_at=pay_by)


def prepare_payment(user, address_id):
    with locked_customer_cart(user) as (cart, order):
        try:
            address = Address.objects.get(pk=address_id, user=user)
        except Address.DoesNotExist as exc:
            raise NotFound("Address not found.") from exc
        created = order is None
        if created:
            order = reserve_order(cart, address)
        return order, current_attempt(order), created


def gateway_session(order, payment):
    # No cart or inventory locks during gateway I/O. Creation is idempotent by reference.
    try:
        session = gateway.lookup_session(payment.reference)
        if session is None:
            if payment.state != Payment.State.CREATING:
                raise GatewayUnavailable()
            session = gateway.create_session(payment.reference, order, payment.expires_at)
    except (TimeoutError, ConnectionError) as exc:
        raise GatewayUnavailable() from exc
    if session.outcome:
        apply_event(gateway.result_event(session))
    return session


def checkout_response(order, payment):
    return {
        "order_id": order.pk, "order_status": order.status, "payment_id": payment.pk,
        "payment_url": payment.payment_url, "payment_url_expires_at": payment.expires_at,
        "expires_at": order.expires_at, "subtotal": str(order.subtotal),
        "shipping_total": str(order.shipping_total), "total_amount": str(order.total_amount),
    }


def checkout(user, address_id, build_absolute_uri):
    gateway.check_configured()
    order, payment, created = prepare_payment(user, address_id)
    # A provider lookup can reveal that the previous attempt has already closed.
    # Allow one replacement in this request without extending the reservation.
    for attempt_number in range(2):
        session = gateway_session(order, payment)
        url = gateway.payment_url(session, build_absolute_uri)
        with transaction.atomic():
            Cart.objects.select_for_update().get(pk=order.cart_id)
            order = Order.objects.select_for_update().get(pk=order.pk)
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            expire_if_due(order)
            if order.status == Order.Status.EXPIRED:
                break
            if order.status in Order.PAID_STATUSES:
                return {"order_id": order.pk, "order_status": order.status}, False
            if payment.state == Payment.State.PROCESSING:
                raise GatewayUnavailable("Payment is processing. Retry checkout to check its status.")
            if payment.state in (Payment.State.CREATING, Payment.State.OPEN):
                if session.expires_at > payment.expires_at or session.expires_at >= order.expires_at:
                    raise GatewayUnavailable("The gateway returned an invalid session expiry.")
                if session.expires_at > timezone.now():
                    payment.session_id = gateway.session_id(session)
                    payment.payment_url = payment.payment_url or url
                    payment.expires_at = session.expires_at
                    payment.state = Payment.State.OPEN
                    payment.save(update_fields=["session_id", "payment_url", "expires_at", "state", "updated_at"])
                    return checkout_response(order, payment), created
                payment.state = Payment.State.EXPIRED
                payment.save(update_fields=["state", "updated_at"])
            if timezone.now() >= order.expires_at - PAYMENT_EXPIRY_MARGIN:
                break
            if attempt_number == 0:
                payment = current_attempt(order)
    if order.status == Order.Status.EXPIRED or timezone.now() >= order.expires_at - PAYMENT_EXPIRY_MARGIN:
        raise PermissionDenied("The payment window has closed for this order.")
    raise GatewayUnavailable()
