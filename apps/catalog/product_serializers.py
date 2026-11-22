from decimal import Decimal
from urllib.parse import quote, urlsplit

from django.conf import settings
from rest_framework import serializers

from common.fields import LocalizedTextField

from .models import Product, ProductImage

MAX_ID = 2**63 - 1


class ProductCreateSerializer(serializers.ModelSerializer):
    title = LocalizedTextField()
    description = LocalizedTextField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    stock = serializers.IntegerField(min_value=0, max_value=2**31 - 1)
    category_id = serializers.IntegerField(min_value=1, max_value=MAX_ID)

    class Meta:
        model = Product
        fields = ("title", "description", "price", "stock", "category_id")


class ProductUpdateSerializer(ProductCreateSerializer):
    class Meta(ProductCreateSerializer.Meta):
        fields = (*ProductCreateSerializer.Meta.fields, "is_published")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image_path", "is_primary")


class ProductImageURLSerializer(ProductImageSerializer):
    image_path = serializers.SerializerMethodField()

    def get_image_path(self, image):
        base_url = settings.PRODUCT_IMAGE_BASE_URL.rstrip("/")
        prefix = urlsplit(base_url).path.strip("/")
        path = image.image_path.removeprefix(f"{prefix}/") if prefix else image.image_path
        return f"{base_url}/{quote(path, safe='/')}"


class ProductReadSerializer(serializers.ModelSerializer):
    title = LocalizedTextField(read_only=True)
    description = LocalizedTextField(read_only=True)
    images = ProductImageURLSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "title", "description", "price", "stock", "is_published",
            "shop_id", "category_id", "images",
        )


class ProductImageCreateSerializer(serializers.Serializer):
    image_path = serializers.CharField(max_length=500)

    def validate_image_path(self, path):
        if (
            any(segment in {"", ".", ".."} for segment in path.split("/"))
            or any(character in path for character in "\\:?#%")
            or any(ord(character) < 32 or ord(character) == 127 for character in path)
        ):
            raise serializers.ValidationError("Provide a relative image path such as products/front.jpg.")
        return path


class ProductImagePrimarySerializer(serializers.Serializer):
    is_primary = serializers.BooleanField()

    def validate_is_primary(self, value):
        if not value:
            raise serializers.ValidationError("Set is_primary to true to select this image.")
        return value


class ProductFilterSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(min_value=1, max_value=MAX_ID, required=False)
    shop_id = serializers.IntegerField(min_value=1, max_value=MAX_ID, required=False)
    min_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    max_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False
    )
    search = serializers.CharField(max_length=255, allow_blank=True, required=False)
    ordering = serializers.ChoiceField(
        choices=("created_at", "-created_at", "price", "-price", "stock", "-stock", "title", "-title"),
        required=False,
    )

    def validate(self, attrs):
        if "min_price" in attrs and "max_price" in attrs and attrs["min_price"] > attrs["max_price"]:
            raise serializers.ValidationError({"max_price": "Must be greater than or equal to min_price."})
        return attrs
