import uuid

from django.db import models


class Payment(models.Model):
    class State(models.TextChoices):
        CREATING = "CREATING"
        OPEN = "OPEN"
        PROCESSING = "PROCESSING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        EXPIRED = "EXPIRED"

    PENDING_STATES = (State.CREATING, State.OPEN, State.PROCESSING)

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=32, default="mock")
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session_id = models.CharField(max_length=255, blank=True)
    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    payment_url = models.URLField(max_length=2000, blank=True)
    expires_at = models.DateTimeField()
    state = models.CharField(max_length=16, choices=State, default=State.CREATING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "transaction_id"], name="payments_provider_transaction"),
            models.UniqueConstraint(fields=["order"], condition=models.Q(state__in=["CREATING", "OPEN", "PROCESSING"]),
                                    name="payments_one_open_per_order"),
        ]


class PaymentEvent(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="events")
    event_id = models.CharField(max_length=255)
    transaction_id = models.CharField(max_length=255)
    outcome = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    attention_reason = models.CharField(max_length=80, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["payment", "event_id"], name="payments_unique_attempt_event")]


class MockSession(models.Model):
    """Durable gateway-side state, keyed by the merchant's idempotency reference."""
    reference = models.UUIDField(unique=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order_reference = models.BigIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    expires_at = models.DateTimeField()
    outcome = models.CharField(max_length=10, blank=True)
