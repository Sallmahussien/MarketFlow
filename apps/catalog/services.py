from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.orders.models import Order, OrderItem

from .models import Category, Product, ProductImage


def active_category(category_id):
    categories = Category.objects.select_for_update(no_key=True).filter(is_active=True)
    if not categories.filter(pk=category_id).first():
        raise ValidationError({"category_id": "Select an active category."})


def locked_product(shop, product_id):
    try:
        return Product.objects.select_for_update().get(pk=product_id, shop=shop)
    except Product.DoesNotExist as error:
        raise NotFound() from error


def product_image(product, image_id):
    try:
        return product.images.get(pk=image_id)
    except ProductImage.DoesNotExist as error:
        raise NotFound() from error


@transaction.atomic
def create_product(shop, values):
    active_category(values["category_id"])
    return Product.objects.create(shop=shop, **values)


@transaction.atomic
def update_product(shop, product_id, values):
    product = locked_product(shop, product_id)
    if "stock" in values and values["stock"] > product.stock:
        # Reserved units may return to this PositiveIntegerField when checkout expires.
        reserved = OrderItem.objects.filter(product=product, order__status=Order.Status.PENDING_PAYMENT)
        reserved_count = reserved.aggregate(count=Sum("quantity", default=0))["count"]
        if values["stock"] + reserved_count > 2**31 - 1:
            raise ValidationError({"stock": "Available and reserved stock exceed the supported quantity."})
    if "category_id" in values:
        active_category(values["category_id"])
    if values.get("is_published") and not product.images.exists():
        raise ValidationError({"is_published": "Add at least one image before publishing."})
    if values:
        for field, value in values.items():
            setattr(product, field, value)
        product.save(update_fields=[*values, "updated_at"])
    return product


@transaction.atomic
def add_image(shop, product_id, image_path):
    product = locked_product(shop, product_id)
    return product.images.create(image_path=image_path, is_primary=not product.images.exists())


@transaction.atomic
def select_primary_image(shop, product_id, image_id):
    product = locked_product(shop, product_id)
    image = product_image(product, image_id)
    if not image.is_primary:
        product.images.filter(is_primary=True).update(is_primary=False, updated_at=timezone.now())
        image.is_primary = True
        image.save(update_fields=["is_primary", "updated_at"])
    return image


@transaction.atomic
def remove_image(shop, product_id, image_id):
    product = locked_product(shop, product_id)
    image = product_image(product, image_id)
    was_primary = image.is_primary
    image.delete()
    remaining = product.images.first()
    if remaining is None:
        if product.is_published:
            product.is_published = False
            product.save(update_fields=["is_published", "updated_at"])
    elif was_primary:
        remaining.is_primary = True
        remaining.save(update_fields=["is_primary", "updated_at"])
