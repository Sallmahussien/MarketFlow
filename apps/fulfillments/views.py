from django.db.models import Prefetch
from rest_framework import generics
from rest_framework.response import Response

from apps.orders.models import OrderItem
from apps.shops.permissions import IsSeller
from common.pagination import StandardPagination
from common.views import LocalizedResponseMixin

from .models import Fulfillment
from .serializers import (
    FulfillmentDetailSerializer,
    FulfillmentListQuerySerializer,
    FulfillmentSummarySerializer,
    FulfillmentUpdateSerializer,
)
from .services import update_fulfillment


class SellerFulfillmentView:
    permission_classes = (IsSeller,)

    def get_queryset(self):
        return Fulfillment.objects.filter(shop__user=self.request.user)


class FulfillmentListView(SellerFulfillmentView, generics.ListAPIView):
    serializer_class = FulfillmentSummarySerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        query = FulfillmentListQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        return super().get_queryset().filter(**query.validated_data).order_by("-created_at", "-pk")


class FulfillmentDetailView(LocalizedResponseMixin, SellerFulfillmentView, generics.RetrieveAPIView):
    serializer_class = FulfillmentDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.method in ("GET", "HEAD"):
            return queryset.select_related("order").prefetch_related(
                Prefetch("items", queryset=OrderItem.objects.select_related("product").order_by("pk")),
            )
        return queryset

    def patch(self, request, *args, **kwargs):
        fulfillment = self.get_object()
        serializer = FulfillmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fulfillment = update_fulfillment(fulfillment, serializer.validated_data)
        return Response(FulfillmentSummarySerializer(fulfillment).data)
