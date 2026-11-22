from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import User
from common.fields import LocalizedTextField

from .models import Shop


class ShopCreateSerializer(serializers.ModelSerializer):
    name = LocalizedTextField()
    description = LocalizedTextField()
    shipping_fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.00"))

    class Meta:
        model = Shop
        fields = ("name", "description", "logo_url", "shipping_fee")


class ShopUpdateSerializer(ShopCreateSerializer):
    class Meta(ShopCreateSerializer.Meta):
        fields = (*ShopCreateSerializer.Meta.fields, "is_active")

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one editable shop field.")
        return attrs


class PublicShopSerializer(serializers.ModelSerializer):
    name = LocalizedTextField(read_only=True)
    description = LocalizedTextField(read_only=True)

    class Meta:
        model = Shop
        fields = ("id", "name", "description", "logo_url", "shipping_fee", "is_active")


class ShopApplicationSerializer(PublicShopSerializer):
    class Meta(PublicShopSerializer.Meta):
        fields = (*PublicShopSerializer.Meta.fields, "status")


class SellerShopSerializer(ShopApplicationSerializer):
    class Meta(ShopApplicationSerializer.Meta):
        fields = (*ShopApplicationSerializer.Meta.fields, "rejection_reason")


class AdminShopListSerializer(PublicShopSerializer):
    class Meta(PublicShopSerializer.Meta):
        fields = (*PublicShopSerializer.Meta.fields, "status", "user_id")


class ShopOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone")


class AdminShopDetailSerializer(serializers.Serializer):
    user = ShopOwnerSerializer(read_only=True)
    shop = SellerShopSerializer(source="*", read_only=True)


class ShopDecisionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(Shop.Status.APPROVED, Shop.Status.REJECTED))
    rejection_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        if attrs["status"] == Shop.Status.REJECTED and not attrs.get("rejection_reason"):
            raise serializers.ValidationError({"rejection_reason": "Provide a reason for rejection."})
        return attrs


class ShopStatusFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Shop.Status.choices, required=False)
