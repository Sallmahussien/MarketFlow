from django.urls import path

from .views import AdminCategoryCreateView, AdminCategoryViewSet, PublicCategoryViewSet

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
]
