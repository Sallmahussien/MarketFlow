from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .models import User


def auth_payload(user, access, refresh, context):
    return {
        "user": ProfileSerializer(user, context=context).data,
        "auth": {"access_token": str(access), "refresh_token": str(refresh)},
    }


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "profile_image", "role")
        read_only_fields = ("id", "username", "email", "role")


class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=(User.Role.CUSTOMER, User.Role.SELLER))

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password", "phone", "role", "profile_image")
        extra_kwargs = {
            "first_name": {"required": True, "allow_blank": False},
            "last_name": {"required": True, "allow_blank": False},
        }

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        user = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs["first_name"],
            last_name=attrs["last_name"],
        )
        try:
            validate_password(attrs["password"], user=user)
        except ValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(**validated_data)
        except IntegrityError as error:
            if User.objects.filter(email__iexact=validated_data["email"]).exists():
                raise serializers.ValidationError({"email": "An account with this email already exists."}) from error
            if User.objects.filter(username=User.normalize_username(validated_data["username"])).exists():
                raise serializers.ValidationError({"username": "An account with this username already exists."}) from error
            raise


class LoginSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        attrs["email"] = User.objects.normalize_email(attrs["email"])
        tokens = super().validate(attrs)
        return auth_payload(self.user, tokens["access"], tokens["refresh"], self.context)


class RefreshSerializer(TokenRefreshSerializer):
    @transaction.atomic
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        try:
            OutstandingToken.objects.select_for_update().get(jti=refresh[api_settings.JTI_CLAIM])
            # Simple JWT rechecks the blacklist after the row has been locked.
            tokens = super().validate(attrs)
        except (OutstandingToken.DoesNotExist, User.DoesNotExist) as error:
            raise AuthenticationFailed("No active account found for the given token.") from error
        return {"access_token": tokens["access"], "refresh_token": tokens["refresh"]}


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError as error:
            raise serializers.ValidationError("Invalid refresh token.") from error

        user = self.context["request"].user
        if str(token.get(api_settings.USER_ID_CLAIM)) != str(getattr(user, api_settings.USER_ID_FIELD)):
            raise serializers.ValidationError("Invalid refresh token.")
        return token

    def save(self):
        self.validated_data["refresh"].blacklist()
