from rest_framework import serializers

from apps.orders.models import OrderItem
from common.fields import LocalizedTextField

from .models import Fulfillment


class FulfillmentListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Fulfillment.Status.choices, required=False)


class FulfillmentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Fulfillment
        fields = ("id", "order_id", "shop_id", "status", "shipping_fee", "carrier_name", "tracking_number")


class FulfillmentItemSerializer(serializers.ModelSerializer):
    order_item_id = serializers.IntegerField(source="pk", read_only=True)
    title = LocalizedTextField(source="product.title", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("order_item_id", "product_id", "title", "quantity", "unit_price")


class FulfillmentDetailSerializer(FulfillmentSummarySerializer):
    items = FulfillmentItemSerializer(many=True, read_only=True)
    delivery_address = serializers.JSONField(source="order.address_snapshot", read_only=True)

    class Meta(FulfillmentSummarySerializer.Meta):
        fields = (*FulfillmentSummarySerializer.Meta.fields, "items", "delivery_address")


class FulfillmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fulfillment
        fields = ("status", "carrier_name", "tracking_number")

    def validate(self, attrs):
        unknown_fields = self.initial_data.keys() - self.fields.keys()
        if unknown_fields:
            raise serializers.ValidationError({field: "Unknown field." for field in sorted(unknown_fields)})
        return attrs
