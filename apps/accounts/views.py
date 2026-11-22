from django.db import transaction
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from common.pagination import StandardPagination
from common.permissions import IsCustomer

from .models import Address
from .serializers import (
    AddressSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RefreshSerializer,
    SignupSerializer,
    auth_payload,
)


class SignupView(generics.CreateAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = SignupSerializer
    throttle_scope = "auth_signup"

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        data = auth_payload(user, refresh.access_token, refresh, self.get_serializer_context())
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "auth_token"


class RefreshView(TokenRefreshView):
    serializer_class = RefreshSerializer
    throttle_scope = "auth_token"


class LogoutView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LogoutSerializer
    throttle_scope = "auth_token"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ProfileSerializer
    http_method_names = ("get", "patch", "head", "options")

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response({"user": serializer.data})

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"user": serializer.data})


class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = (IsCustomer,)
    serializer_class = AddressSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        addresses = Address.objects.filter(user=self.request.user).order_by("pk")
        if self.action == "partial_update":
            return addresses.select_for_update()
        return addresses

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
