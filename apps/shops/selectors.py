from .models import Shop


def public_shops():
    return Shop.objects.filter(status=Shop.Status.APPROVED, is_active=True).order_by("pk")


def admin_shops(status=None):
    shops = Shop.objects.order_by("pk")
    if status is not None:
        shops = shops.filter(status=status)
    return shops
