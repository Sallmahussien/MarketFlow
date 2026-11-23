from django.db.models import Case, OuterRef, Subquery, Value, When

from .models import Payment, PaymentEvent


ATTENTION_REASONS = {
    "late_success": "PAYMENT_AFTER_ORDER_EXPIRATION",
    "additional_charge": "ADDITIONAL_CHARGE",
}


def admin_payments(*, status=None, requires_attention=None):
    flagged_events = PaymentEvent.objects.filter(
        payment_id=OuterRef("pk"),
        outcome=Payment.State.SUCCESS,
        attention_reason__in=ATTENTION_REASONS,
    ).order_by("-received_at", "-pk")
    payments = Payment.objects.annotate(
        status=Case(
            When(state__in=Payment.PENDING_STATES, then=Value("PENDING")),
            default="state",
        ),
        attention_reason_code=Subquery(flagged_events.values("attention_reason")[:1]),
    )
    if status is not None:
        payments = payments.filter(status=status)
    if requires_attention is not None:
        payments = payments.filter(attention_reason_code__isnull=not requires_attention)
    return payments.order_by("-created_at", "-pk")
