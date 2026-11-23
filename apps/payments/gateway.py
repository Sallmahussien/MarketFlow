import hmac
import json

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import MockSession


class GatewayUnavailable(APIException):
    status_code = 503
    default_detail = "Payment session could not be verified. Retry checkout."


class MockEventSerializer(serializers.Serializer):
    event_id = serializers.CharField(max_length=255)
    transaction_id = serializers.UUIDField()
    order_reference = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    status = serializers.ChoiceField(choices=("SUCCESS", "FAILED"))
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(max_length=3)


class MockGateway:
    name = "mock"

    def check_configured(self):
        if not settings.MOCK_PAYMENT_SECRET:
            raise GatewayUnavailable("Set MOCK_PAYMENT_SECRET to enable the mock payment gateway.")

    def lookup_session(self, reference):
        return MockSession.objects.filter(reference=reference).first()

    def create_session(self, reference, order, pay_by):
        if timezone.now() >= pay_by:
            raise GatewayUnavailable("The payment window has closed.")
        session, _ = MockSession.objects.get_or_create(reference=reference, defaults={
            "order_reference": order.pk, "amount": order.total_amount,
            "currency": order.currency, "expires_at": pay_by,
        })
        return session

    def payment_url(self, session, build_absolute_uri):
        return build_absolute_uri(reverse("checkout:mock-session", args=[session.token]))

    def signature(self, body):
        self.check_configured()
        return hmac.digest(settings.MOCK_PAYMENT_SECRET.encode(), body, "sha256").hex()

    def verify_event(self, body, signature):
        if not hmac.compare_digest(self.signature(body).encode(), signature.encode()):
            raise PermissionDenied("Invalid payment callback signature.")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationError("Invalid callback JSON.") from exc
        serializer = MockEventSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        event = serializer.validated_data
        try:
            session = MockSession.objects.get(transaction_id=event["transaction_id"])
        except MockSession.DoesNotExist as exc:
            raise ValidationError("Unknown payment reference.") from exc
        event["reference"] = session.reference
        return event

    def session_id(self, session):
        return str(session.token)

    def result_event(self, session):
        body, signature = self.signed_result(session)
        return self.verify_event(body, signature)

    def signed_result(self, session):
        body = json.dumps({
            "event_id": f"{session.transaction_id}-{session.outcome}",
            "transaction_id": str(session.transaction_id), "order_reference": str(session.order_reference),
            "amount": str(session.amount), "currency": session.currency, "status": session.outcome,
        }).encode()
        return body, self.signature(body)


gateway = MockGateway()
