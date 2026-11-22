from django.urls import path

from .views import AddressViewSet

app_name = "addresses"

urlpatterns = [
    path("", AddressViewSet.as_view({"get": "list", "post": "create"}), name="list"),
    path(
        "<int:pk>/",
        AddressViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="detail",
    ),
]
