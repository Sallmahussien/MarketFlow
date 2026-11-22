from rest_framework import serializers

from common.fields import LocalizedTextField

from .models import Category


class CategoryCreateSerializer(serializers.ModelSerializer):
    name = LocalizedTextField()
    description = LocalizedTextField()

    class Meta:
        model = Category
        fields = ("name", "description", "icon_url")
        extra_kwargs = {"icon_url": {"allow_blank": False}}


class CategoryUpdateSerializer(CategoryCreateSerializer):
    class Meta(CategoryCreateSerializer.Meta):
        fields = (*CategoryCreateSerializer.Meta.fields, "is_active")

    def update(self, instance, validated_data):
        if validated_data:
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save(update_fields=[*validated_data, "updated_at"])
            instance.refresh_from_db()
        return instance


class CategoryReadSerializer(serializers.ModelSerializer):
    name = LocalizedTextField(read_only=True)
    description = LocalizedTextField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "description", "icon_url", "is_active")
