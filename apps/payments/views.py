from rest_framework import generics

from common.pagination import StandardPagination
from common.permissions import IsMarketplaceAdmin

from .selectors import admin_payments
from .serializers import AdminPaymentFilterSerializer, AdminPaymentSerializer


class AdminPaymentListView(generics.ListAPIView):
    permission_classes = (IsMarketplaceAdmin,)
    pagination_class = StandardPagination
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        filters = AdminPaymentFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return admin_payments(**filters.validated_data)
