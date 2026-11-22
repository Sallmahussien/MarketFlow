from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.i18n import resolve_language
from common.pagination import StandardPagination
from common.views import LocalizedResponseMixin

from .models import Product, ProductImage
from .permissions import HasApprovedShop
from .product_serializers import (
    ProductCreateSerializer,
    ProductFilterSerializer,
    ProductImageCreateSerializer,
    ProductImagePrimarySerializer,
    ProductImageSerializer,
    ProductReadSerializer,
    ProductUpdateSerializer,
)
from .selectors import filter_public_products, public_products, seller_products
from .services import add_image, create_product, remove_image, select_primary_image, update_product


class ProductListCreateView(LocalizedResponseMixin, generics.ListCreateAPIView):
    pagination_class = StandardPagination

    def get_permissions(self):
        return [HasApprovedShop()] if self.request.method == "POST" else [AllowAny()]

    def get_serializer_class(self):
        return ProductCreateSerializer if self.request.method == "POST" else ProductReadSerializer

    def get_queryset(self):
        filters = ProductFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        language = resolve_language(self.request.headers.get("Accept-Language"))
        return filter_public_products(public_products(), filters.validated_data, language)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = create_product(self.approved_shop, serializer.validated_data)
        response = ProductReadSerializer(product, context=self.get_serializer_context())
        return Response(response.data, status=status.HTTP_201_CREATED)


class ProductDetailView(LocalizedResponseMixin, generics.RetrieveUpdateAPIView):
    http_method_names = ("get", "patch", "head", "options")

    def get_permissions(self):
        return [HasApprovedShop()] if self.request.method == "PATCH" else [AllowAny()]

    def get_serializer_class(self):
        return ProductUpdateSerializer if self.request.method == "PATCH" else ProductReadSerializer

    def get_queryset(self):
        if self.request.method == "PATCH":
            return Product.objects.filter(shop=self.approved_shop)
        return public_products()

    def partial_update(self, request, *args, **kwargs):
        product = self.get_object()
        serializer = self.get_serializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = update_product(self.approved_shop, product.pk, serializer.validated_data)
        return Response(ProductReadSerializer(product, context=self.get_serializer_context()).data)


class SellerProductViewSet(LocalizedResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (HasApprovedShop,)
    serializer_class = ProductReadSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return seller_products(self.approved_shop)


class ProductImageCreateView(generics.CreateAPIView):
    permission_classes = (HasApprovedShop,)
    serializer_class = ProductImageCreateSerializer

    def create(self, request, *args, **kwargs):
        product = generics.get_object_or_404(Product, pk=kwargs["product_id"], shop=self.approved_shop)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = add_image(self.approved_shop, product.pk, **serializer.validated_data)
        return Response(ProductImageSerializer(image).data, status=status.HTTP_201_CREATED)


class ProductImageDetailView(generics.GenericAPIView):
    permission_classes = (HasApprovedShop,)
    serializer_class = ProductImagePrimarySerializer
    lookup_url_kwarg = "image_id"

    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs["product_id"], product__shop=self.approved_shop)

    def patch(self, request, product_id, image_id):
        image = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = select_primary_image(self.approved_shop, product_id, image.pk)
        return Response(ProductImageSerializer(image).data)

    def delete(self, request, product_id, image_id):
        remove_image(self.approved_shop, product_id, image_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
