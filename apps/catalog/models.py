from django.db import models


class Category(models.Model):
    name = models.JSONField()
    description = models.JSONField()
    icon_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Product(models.Model):
    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    title = models.JSONField()
    description = models.JSONField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="catalog_product_price_positive"),
        ]


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image_path = models.CharField(max_length=500)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("product",), condition=models.Q(is_primary=True), name="catalog_one_primary_image"
            ),
        ]
