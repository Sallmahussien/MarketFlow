from rest_framework import generics, status
from rest_framework.response import Response

from common.permissions import IsCustomer
from common.views import LocalizedResponseMixin

from .serializers import CartAddItemSerializer, CartReadSerializer, CartUpdateItemSerializer
from .services import add_item, clear_cart, read_cart, remove_item, set_item_quantity


class CartResponseView(LocalizedResponseMixin, generics.GenericAPIView):
    permission_classes = (IsCustomer,)

    def cart_response(self, cart):
        return Response(CartReadSerializer(cart, context=self.get_serializer_context()).data)


class CartView(CartResponseView):
    serializer_class = CartAddItemSerializer

    def get(self, request):
        return self.cart_response(read_cart(request.user))

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.cart_response(add_item(request.user, **serializer.validated_data))

    def delete(self, request):
        clear_cart(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemView(CartResponseView):
    serializer_class = CartUpdateItemSerializer

    def patch(self, request, item_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.cart_response(set_item_quantity(request.user, item_id, **serializer.validated_data))

    def delete(self, request, item_id):
        return self.cart_response(remove_item(request.user, item_id))
