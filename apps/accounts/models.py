from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower


class AccountManager(UserManager):
    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).lower()

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        CUSTOMER = "CUSTOMER", "Customer"
        SELLER = "SELLER", "Seller"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    profile_image = models.CharField(max_length=255, blank=True, null=True)
    role = models.CharField(max_length=10, choices=Role, default=Role.CUSTOMER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)
