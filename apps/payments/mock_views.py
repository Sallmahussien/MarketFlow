from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from rest_framework.exceptions import APIException

from apps.carts.models import Cart
from apps.orders.models import Order

from .callbacks import receive_callback
from .gateway import gateway
from .models import MockSession, Payment


@transaction.atomic
def submit_result(session, outcome):
    payment = Payment.objects.select_related("order").get(reference=session.reference)
    Cart.objects.select_for_update().get(pk=payment.order.cart_id)
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    session = MockSession.objects.select_for_update().get(pk=session.pk)
    if session.outcome:
        return session
    if (order.status != Order.Status.PENDING_PAYMENT or payment.state != Payment.State.OPEN
            or timezone.now() >= min(session.expires_at, order.expires_at)):
        return None
    session.outcome = outcome
    session.save(update_fields=["outcome"])
    payment.state = Payment.State.PROCESSING
    payment.save(update_fields=["state", "updated_at"])
    # The in-process mock can commit its simulated charge and signed delivery together.
    # A crash during submission leaves the customer able to retry the same link.
    receive_callback(*gateway.signed_result(session))
    return session


@never_cache
@require_http_methods(["GET", "POST"])
def mock_session(request, token):
    session = get_object_or_404(MockSession, token=token)
    context = {"session": session}
    status = 200
    if request.method == "POST":
        outcome = request.POST.get("outcome")
        if outcome not in ("SUCCESS", "FAILED"):
            context["message"] = "Choose a payment outcome."
            status = 400
        else:
            try:
                gateway.check_configured()
                submitted = submit_result(session, outcome)
                if submitted:
                    context["message"] = f"Mock payment result: {submitted.outcome}."
                else:
                    context["message"] = "This session is closed."
                    status = 409
            except APIException as exc:
                context["message"] = str(exc.detail)
                status = exc.status_code
    elif session.outcome:
        context["message"] = f"Mock payment result: {session.outcome}."
    elif session.expires_at <= timezone.now():
        context["message"] = "This session has expired."
    elif not Payment.objects.filter(reference=session.reference, state=Payment.State.OPEN,
                                    order__status=Order.Status.PENDING_PAYMENT).exists():
        context["message"] = "This session is closed."
    response = render(request, "payments/mock_session.html", context, status=status)
    # Preserve the origin for same-origin form posts while keeping the session URL private across origins.
    response.headers["Referrer-Policy"] = "same-origin"
    return response
