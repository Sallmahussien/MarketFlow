from rest_framework import serializers

from common.fields import LocalizedTextField


class CartUpdateItemSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=2**31 - 1)


class CartAddItemSerializer(CartUpdateItemSerializer):
    product_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)


class CartItemReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    title = LocalizedTextField(read_only=True)
    shop_id = serializers.IntegerField()
    stock = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    count = serializers.IntegerField()
    is_available = serializers.BooleanField()
    line_total = serializers.DecimalField(max_digits=None, decimal_places=2)


class CartReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    item_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    sub_total = serializers.DecimalField(max_digits=None, decimal_places=2)
    total_shipping = serializers.DecimalField(max_digits=None, decimal_places=2)
    total = serializers.DecimalField(max_digits=None, decimal_places=2)
    items = CartItemReadSerializer(many=True)
