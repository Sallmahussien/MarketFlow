from django.db.models import Case, OuterRef, Subquery, Value, When

from apps.payments.models import Payment

from .models import Order


def customer_orders(user):
    # A successful charge remains relevant even if a newer attempt later closed or failed.
    relevant_payment = Payment.objects.filter(order_id=OuterRef("pk")).order_by(
        Case(When(state=Payment.State.SUCCESS, then=Value(0)), default=Value(1)), "-pk",
    )
    return Order.objects.filter(user=user).annotate(payment_state=Subquery(relevant_payment.values("state")[:1]))
