from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from common.pagination import CatalogPagination
from common.permissions import IsMarketplaceAdmin
from common.views import LocalizedResponseMixin

from .models import Category
from .serializers import CategoryCreateSerializer, CategoryReadSerializer, CategoryUpdateSerializer


class PublicCategoryViewSet(LocalizedResponseMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = (AllowAny,)
    serializer_class = CategoryReadSerializer
    pagination_class = CatalogPagination
    queryset = Category.objects.filter(is_active=True).order_by("pk")


class AdminCategoryCreateView(LocalizedResponseMixin, generics.CreateAPIView):
    permission_classes = (IsMarketplaceAdmin,)
    serializer_class = CategoryCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        response = CategoryReadSerializer(category, context=self.get_serializer_context())
        return Response(response.data, status=status.HTTP_201_CREATED)


class AdminCategoryViewSet(
    LocalizedResponseMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    permission_classes = (IsMarketplaceAdmin,)
    serializer_class = CategoryUpdateSerializer
    queryset = Category.objects.all()

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(CategoryReadSerializer(category, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        if instance.is_active:
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
