from decimal import Decimal

from apps.shops.models import Shop

ZERO_MONEY = Decimal("0.00")


def product_is_available(product, quantity):
    return (
        product.is_published
        and product.stock >= quantity
        and product.shop.status == Shop.Status.APPROVED
        and product.shop.is_active
        and product.category.is_active
    )


def cart_contents(cart):
    lines = cart.items.select_related("product__shop", "product__category").order_by("pk")
    items = []
    total_count = 0
    subtotal = ZERO_MONEY
    shipping_by_shop = {}
    for line in lines:
        product = line.product
        available = product_is_available(product, line.quantity)
        line_total = product.price * line.quantity
        items.append({
            "id": line.pk,
            "product_id": product.pk,
            "title": product.title,
            "shop_id": product.shop_id,
            "stock": product.stock,
            "price": product.price,
            "count": line.quantity,
            "is_available": available,
            "line_total": line_total,
        })
        total_count += line.quantity
        if available:
            subtotal += line_total
            shipping_by_shop[product.shop_id] = product.shop.shipping_fee

    shipping = sum(shipping_by_shop.values(), ZERO_MONEY)
    return {
        "id": cart.pk,
        "item_count": len(items),
        "total_count": total_count,
        "sub_total": subtotal,
        "total_shipping": shipping,
        "total": subtotal + shipping,
        "items": items,
    }
