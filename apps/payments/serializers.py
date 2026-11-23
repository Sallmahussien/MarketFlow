from rest_framework import serializers

from .models import Payment
from .selectors import ATTENTION_REASONS


class AdminPaymentFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("PENDING", Payment.State.SUCCESS, Payment.State.FAILED), required=False)
    requires_attention = serializers.ChoiceField(choices=("true", "false"), required=False)

    def validate_requires_attention(self, value):
        return value == "true"


class AdminPaymentSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    requires_attention = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()

    def get_requires_attention(self, payment):
        return payment.attention_reason_code is not None

    def get_reason(self, payment):
        return ATTENTION_REASONS.get(payment.attention_reason_code)

    class Meta:
        model = Payment
        fields = ("id", "order_id", "transaction_id", "status", "requires_attention", "reason")
