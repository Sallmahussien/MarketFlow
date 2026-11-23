from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.catalog.models import Product
from apps.orders.reservations import locked_customer_cart

from .models import Cart, CartItem
from .selectors import cart_contents, product_is_available


def read_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
    return cart_contents(cart)


def get_item(cart, item_id):
    try:
        return cart.items.select_related("product__shop", "product__category").get(pk=item_id)
    except CartItem.DoesNotExist as error:
        raise NotFound() from error


def validate_quantity(product, count):
    if not product_is_available(product, count):
        raise ValidationError({"count": "The product is unavailable or has insufficient stock."})


def touch_cart(cart):
    Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now())


def add_item(user, product_id, count):
    with locked_customer_cart(user, editing=True) as (cart, _):
        try:
            product = Product.objects.select_related("shop", "category").get(pk=product_id)
        except Product.DoesNotExist as error:
            raise NotFound("Product not found.") from error
        item = cart.items.filter(product=product).first()
        quantity = count + item.quantity if item else count
        validate_quantity(product, quantity)
        if item is None:
            cart.items.create(product=product, quantity=quantity)
        else:
            item.quantity = quantity
            item.save(update_fields=["quantity", "updated_at"])
        touch_cart(cart)
        return cart_contents(cart)


def set_item_quantity(user, item_id, count):
    with locked_customer_cart(user, editing=True) as (cart, _):
        item = get_item(cart, item_id)
        validate_quantity(item.product, count)
        item.quantity = count
        item.save(update_fields=["quantity", "updated_at"])
        touch_cart(cart)
        return cart_contents(cart)


def remove_item(user, item_id):
    with locked_customer_cart(user, editing=True) as (cart, _):
        get_item(cart, item_id).delete()
        touch_cart(cart)
        return cart_contents(cart)


def clear_cart(user):
    with locked_customer_cart(user, editing=True) as (cart, _):
        cart.items.all().delete()
        touch_cart(cart)
