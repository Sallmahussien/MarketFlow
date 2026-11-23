from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.callbacks import receive_callback
from common.permissions import IsCustomer

from .checkout import checkout


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
