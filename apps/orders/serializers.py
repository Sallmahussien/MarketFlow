from rest_framework import serializers

from apps.fulfillments.models import Fulfillment
from apps.payments.models import Payment
from common.fields import LocalizedTextField

from .models import Order, OrderItem


class OrderListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
    ordering = serializers.ChoiceField(choices=("created_at", "-created_at"), default="-created_at")


class OrderSummarySerializer(serializers.ModelSerializer):
    payment_status = serializers.SerializerMethodField()

    def get_payment_status(self, order):
        if order.payment_state in Payment.PENDING_STATES:
            return "PENDING"
        return order.payment_state

    class Meta:
        model = Order
        fields = ("id", "status", "subtotal", "shipping_total", "total_amount", "payment_status", "created_at")


class OrderListSerializer(OrderSummarySerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta(OrderSummarySerializer.Meta):
        fields = (*OrderSummarySerializer.Meta.fields, "items_count")


class OrderItemSerializer(serializers.ModelSerializer):
    title = LocalizedTextField(source="product.title", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_id", "title", "quantity", "unit_price", "status", "fulfillment_id")


class OrderFulfillmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fulfillment
        fields = ("id", "shop_id", "status", "shipping_fee", "tracking_number", "carrier_name")


class OrderDetailSerializer(OrderSummarySerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    fulfillments = OrderFulfillmentSerializer(many=True, read_only=True)

    class Meta(OrderSummarySerializer.Meta):
        fields = (*OrderSummarySerializer.Meta.fields, "address_snapshot", "items", "fulfillments", "expires_at")
