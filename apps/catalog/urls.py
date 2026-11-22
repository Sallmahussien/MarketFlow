from django.urls import path

from .product_views import (
    ProductDetailView,
    ProductImageCreateView,
    ProductImageDetailView,
    ProductListCreateView,
    SellerProductViewSet,
)
from .category_views import AdminCategoryCreateView, AdminCategoryViewSet, PublicCategoryViewSet

app_name = "catalog"

urlpatterns = [
    path("categories/", PublicCategoryViewSet.as_view({"get": "list"}), name="category-list"),
    path(
        "categories/<int:pk>/",
        PublicCategoryViewSet.as_view({"get": "retrieve"}),
        name="category-detail",
    ),
    path("admin/categories/", AdminCategoryCreateView.as_view(), name="admin-category-create"),
    path(
        "admin/categories/<int:pk>/",
        AdminCategoryViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="admin-category-detail",
    ),
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("seller/products/", SellerProductViewSet.as_view({"get": "list"}), name="seller-product-list"),
    path(
        "seller/products/<int:pk>/",
        SellerProductViewSet.as_view({"get": "retrieve"}),
        name="seller-product-detail",
    ),
    path("products/<int:product_id>/images/", ProductImageCreateView.as_view(), name="product-image-create"),
    path(
        "products/<int:product_id>/images/<int:image_id>/",
        ProductImageDetailView.as_view(),
        name="product-image-detail",
    ),
]
