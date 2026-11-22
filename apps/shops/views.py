from django.utils.cache import patch_vary_headers
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Shop
from .permissions import IsMarketplaceAdmin, IsSeller
from .selectors import admin_shops, public_shops
from .serializers import (
    AdminShopDetailSerializer,
    AdminShopListSerializer,
    PublicShopSerializer,
    SellerShopSerializer,
    ShopApplicationSerializer,
    ShopCreateSerializer,
    ShopDecisionSerializer,
    ShopStatusFilterSerializer,
    ShopUpdateSerializer,
)
from .services import create_application, decide_application, update_own_shop


class LocalizedResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_vary_headers(response, ("Accept-Language",))
        return response


class ShopListCreateView(LocalizedResponseMixin, generics.ListCreateAPIView):
    def get_permissions(self):
        return [IsSeller()] if self.request.method == "POST" else [AllowAny()]

    def get_queryset(self):
        return public_shops()

    def get_serializer_class(self):
        return ShopCreateSerializer if self.request.method == "POST" else PublicShopSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = create_application(request.user, serializer.validated_data)
        response = ShopApplicationSerializer(shop, context=self.get_serializer_context())
        return Response(response.data, status=status.HTTP_201_CREATED)


class OwnShopView(LocalizedResponseMixin, generics.RetrieveUpdateAPIView):
    permission_classes = (IsSeller,)
    http_method_names = ("get", "patch", "head", "options")

    def get_object(self):
        return generics.get_object_or_404(Shop, user=self.request.user)

    def get_serializer_class(self):
        return ShopUpdateSerializer if self.request.method == "PATCH" else SellerShopSerializer

    def partial_update(self, request, *args, **kwargs):
        shop = self.get_object()
        serializer = self.get_serializer(shop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        shop = update_own_shop(shop, serializer.validated_data)
        return Response(SellerShopSerializer(shop, context=self.get_serializer_context()).data)


class PublicShopDetailView(LocalizedResponseMixin, generics.RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PublicShopSerializer

    def get_queryset(self):
        return public_shops()


class AdminShopListView(LocalizedResponseMixin, generics.ListAPIView):
    permission_classes = (IsMarketplaceAdmin,)
    serializer_class = AdminShopListSerializer

    def get_queryset(self):
        filters = ShopStatusFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return admin_shops(**filters.validated_data)


class AdminShopDetailView(LocalizedResponseMixin, generics.RetrieveUpdateAPIView):
    permission_classes = (IsMarketplaceAdmin,)
    http_method_names = ("get", "patch", "head", "options")

    def get_queryset(self):
        return admin_shops().select_related("user")

    def get_serializer_class(self):
        return ShopDecisionSerializer if self.request.method == "PATCH" else AdminShopDetailSerializer

    def partial_update(self, request, *args, **kwargs):
        shop = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = decide_application(shop, **serializer.validated_data)
        return Response(SellerShopSerializer(shop, context=self.get_serializer_context()).data)
