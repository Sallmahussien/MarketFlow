from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.accounts.serializers import AddressSerializer
from apps.carts.models import Cart
from apps.carts.selectors import product_is_available
from apps.catalog.models import Product
from apps.payments.models import Payment

from .models import Order, OrderItem


def expire_if_due(order):
    """Caller holds the cart and order locks, always acquired in that order."""
    if order.status != Order.Status.PENDING_PAYMENT or order.expires_at > timezone.now():
        return False
    for item in order.items.order_by("product_id"):
        Product.objects.filter(pk=item.product_id).update(stock=F("stock") + item.quantity)
    order.payments.filter(state__in=(Payment.State.CREATING, Payment.State.OPEN)).update(
        state=Payment.State.EXPIRED, updated_at=timezone.now(),
    )
    order.status = Order.Status.EXPIRED
    order.save(update_fields=["status", "updated_at"])
    return True


@transaction.atomic
def expire_order(cart_id, order_id):
    Cart.objects.select_for_update().get(pk=cart_id)
    order = Order.objects.select_for_update().get(pk=order_id)
    return expire_if_due(order)


@contextmanager
def locked_customer_cart(user, *, editing=False):
    error = None
    with transaction.atomic():
        cart, _ = Cart.objects.select_for_update().get_or_create(user=user, is_active=True)
        pending = cart.orders.select_for_update().filter(status=Order.Status.PENDING_PAYMENT).first()
        if pending and expire_if_due(pending):
            pending = None
        if editing and pending:
            raise PermissionDenied("Your cart is reserved for a pending order.")
        # Preserve an overdue reservation's release even if the new request is invalid.
        try:
            with transaction.atomic():
                yield cart, pending
        except APIException as exc:
            error = exc
    if error:
        raise error


def reserve_order(cart, address):
    quantities = dict(cart.items.values_list("product_id", "quantity"))
    if not quantities:
        raise ValidationError("Your cart is empty.")
    products = list(Product.objects.select_related("shop", "category").select_for_update(of=("self",))
                    .filter(pk__in=quantities).order_by("pk"))
    shipping = {}
    subtotal = Decimal("0.00")
    items = []
    for product in products:
        count = quantities[product.pk]
        if not product_is_available(product, count):
            raise ValidationError({"cart": f"Product {product.pk} is unavailable or has insufficient stock."})
        shipping[product.shop_id] = product.shop.shipping_fee
        subtotal += product.price * count
        items.append(OrderItem(product=product, shop_id=product.shop_id, quantity=count, unit_price=product.price))
        product.stock -= count
    if len(products) != len(quantities):
        raise ValidationError("A product in your cart is no longer available.")
    shipping_total = sum(shipping.values())
    total = subtotal + shipping_total
    if total >= 10 ** 10:
        raise ValidationError("The total exceeds the supported order amount.")
    snapshot = dict(AddressSerializer(address).data)
    snapshot.pop("id")
    now = timezone.now()
    order = Order.objects.create(
        user_id=cart.user_id, cart=cart, address_snapshot=snapshot, created_at=now,
        expires_at=now + timedelta(minutes=30), subtotal=subtotal, shipping_total=shipping_total,
        total_amount=total, shipping_by_shop={str(shop): str(fee) for shop, fee in shipping.items()},
    )
    for item in items:
        item.order = order
    OrderItem.objects.bulk_create(items)
    Product.objects.bulk_update(products, ["stock"])
    return order
