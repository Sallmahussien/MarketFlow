from django.db.models import Q, TextField, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, NullIf, Trim

from apps.shops.models import Shop

from .models import Product


def public_products():
    return Product.objects.filter(
        is_published=True,
        stock__gt=0,
        shop__status=Shop.Status.APPROVED,
        shop__is_active=True,
        category__is_active=True,
    ).prefetch_related("images")


def seller_products(shop):
    return Product.objects.filter(shop=shop).prefetch_related("images").order_by("-created_at", "-pk")


def localized_expression(field, language):
    english = KeyTextTransform("en", field)
    if language == "en":
        return english
    return Coalesce(
        NullIf(Trim(KeyTextTransform(language, field)), Value("", output_field=TextField())),
        english,
    )


def filter_public_products(products, filters, language):
    query = {
        lookup: filters[name]
        for name, lookup in (
            ("category_id", "category_id"), ("shop_id", "shop_id"),
            ("min_price", "price__gte"), ("max_price", "price__lte"),
        )
        if name in filters
    }
    products = products.filter(**query)
    ordering = filters.get("ordering", "-created_at")
    direction = "-" if ordering.startswith("-") else ""
    sort_field = ordering.removeprefix("-")
    search = filters.get("search")
    if search or sort_field == "title":
        products = products.alias(localized_title=localized_expression("title", language))
    if search:
        products = products.alias(localized_description=localized_expression("description", language)).filter(
            Q(localized_title__icontains=search) | Q(localized_description__icontains=search)
        )
    if sort_field == "title":
        sort_field = "localized_title"
    return products.order_by(f"{direction}{sort_field}", f"{direction}pk")
