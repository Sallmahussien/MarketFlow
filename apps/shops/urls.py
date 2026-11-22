from django.urls import path

from .views import AdminShopDetailView, AdminShopListView, OwnShopView, PublicShopDetailView, ShopListCreateView

app_name = "shops"

urlpatterns = [
    path("shops/", ShopListCreateView.as_view(), name="list-create"),
    path("shops/me/", OwnShopView.as_view(), name="own"),
    path("shops/<int:pk>/", PublicShopDetailView.as_view(), name="public-detail"),
    path("admin/shops/", AdminShopListView.as_view(), name="admin-list"),
    path("admin/shops/<int:pk>/", AdminShopDetailView.as_view(), name="admin-detail"),
]
