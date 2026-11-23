from django.db.models import Prefetch, Sum
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.fulfillments.models import Fulfillment
from apps.payments.callbacks import receive_callback
from common.pagination import StandardPagination
from common.permissions import IsCustomer
from common.views import LocalizedResponseMixin

from .checkout import checkout
from .models import OrderItem
from .selectors import customer_orders
from .serializers import OrderDetailSerializer, OrderListQuerySerializer, OrderListSerializer


class CheckoutRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)


class CheckoutView(APIView):
    permission_classes = (IsCustomer,)

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result, created = checkout(request.user, serializer.validated_data["address_id"], request.build_absolute_uri)
        return Response(result, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CallbackView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        receive_callback(request.body, request.headers.get("X-Mock-Signature", ""))
        return Response({"received": True})


class OrderListView(generics.ListAPIView):
    permission_classes = (IsCustomer,)
    serializer_class = OrderListSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        query = OrderListQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        orders = customer_orders(self.request.user)
        if "status" in filters:
            orders = orders.filter(status=filters["status"])
        ordering = filters["ordering"]
        return orders.annotate(items_count=Sum("items__quantity", default=0)).order_by(
            ordering, "-pk" if ordering.startswith("-") else "pk",
        )


class OrderDetailView(LocalizedResponseMixin, generics.RetrieveAPIView):
    permission_classes = (IsCustomer,)
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        return customer_orders(self.request.user).prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product").order_by("pk")),
            Prefetch("fulfillments", queryset=Fulfillment.objects.order_by("pk")),
        )
