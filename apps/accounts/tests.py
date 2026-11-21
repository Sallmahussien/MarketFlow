from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import User


class AuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.signup_data = {
            "username": "salma",
            "email": "Salma@example.com",
            "first_name": "Salma",
            "last_name": "Ahmed",
            "password": "StrongPassword123!",
            "phone": "01012345678",
            "role": "CUSTOMER",
        }

    def signup(self):
        response = self.client.post(reverse("accounts:signup"), self.signup_data, format="json")
        self.assertEqual(response.status_code, 201)
        return response.data

    def authorize(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_signup_login_and_profile(self):
        signup = self.signup()
        user = User.objects.get()
        self.assertNotIn("password", signup["user"])
        self.assertIsNone(signup["user"]["profile_image"])
        self.assertTrue(user.check_password(self.signup_data["password"]))
        response = self.client.post(
            reverse("accounts:login"),
            {"email": "SALMA@example.com", "password": self.signup_data["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"], signup["user"])
        self.authorize(response.data["auth"]["access_token"])
        profile = self.client.get(reverse("accounts:profile"))
        self.assertEqual(profile.data, {"user": signup["user"]})

    def test_public_signup_rejects_admin_and_weak_password(self):
        for invalid_fields, field in (({"role": "ADMIN"}, "role"), ({"password": "123"}, "password")):
            with self.subTest(field=field):
                response = self.client.post(
                    reverse("accounts:signup"), self.signup_data | invalid_fields, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(User.objects.exists())

    def test_seller_signup_and_duplicate_email(self):
        self.signup_data["role"] = "SELLER"
        self.assertEqual(self.signup()["user"]["role"], "SELLER")
        response = self.client.post(
            reverse("accounts:signup"),
            self.signup_data | {"username": "other", "email": "SALMA@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_invalid_credentials_have_same_response(self):
        self.signup()
        errors = []
        for email in ("Salma@example.com", "unknown@example.com"):
            response = self.client.post(
                reverse("accounts:login"), {"email": email, "password": "wrong"}, format="json"
            )
            self.assertEqual(response.status_code, 401)
            errors.append(response.data)
        self.assertEqual(errors[0], errors[1])

    def test_profile_requires_auth_and_ignores_read_only_fields(self):
        profile_url = reverse("accounts:profile")
        self.assertEqual(self.client.get(profile_url).status_code, 401)
        self.assertEqual(self.client.patch(profile_url, {}, format="json").status_code, 401)
        self.authorize(self.signup()["auth"]["access_token"])
        response = self.client.patch(
            profile_url,
            {"first_name": "Sara", "role": "ADMIN", "email": "other@example.com", "username": "other"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["first_name"], "Sara")
        user = User.objects.get()
        self.assertEqual((user.role, user.email, user.username), ("CUSTOMER", "salma@example.com", "salma"))

    def test_refresh_rotation_and_logout(self):
        refresh_url = reverse("accounts:refresh")
        logout_url = reverse("accounts:logout")
        original = {"refresh": self.signup()["auth"]["refresh_token"]}
        self.assertEqual(self.client.post(logout_url, original, format="json").status_code, 401)
        response = self.client.post(refresh_url, original, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(refresh_url, original, format="json").status_code, 401)
        rotated = {"refresh": response.data["refresh_token"]}
        self.authorize(response.data["access_token"])
        self.assertEqual(self.client.post(logout_url, rotated, format="json").status_code, 204)
        self.client.credentials()
        self.assertEqual(self.client.post(refresh_url, rotated, format="json").status_code, 401)

    def test_profile_image_path_can_be_set_and_cleared(self):
        self.signup_data["profile_image"] = "profiles/original.png"
        signup = self.signup()
        self.assertEqual(signup["user"]["profile_image"], "profiles/original.png")
        self.authorize(signup["auth"]["access_token"])
        profile_url = reverse("accounts:profile")
        path = "profiles/avatar.png"
        response = self.client.patch(profile_url, {"profile_image": path}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["profile_image"], path)
        self.assertEqual(User.objects.get().profile_image, path)

        response = self.client.patch(profile_url, {"profile_image": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["user"]["profile_image"])

    def test_logout_rejects_another_accounts_token(self):
        first = self.signup()["auth"]
        self.signup_data.update(username="other", email="other@example.com")
        second = self.signup()["auth"]
        self.authorize(first["access_token"])
        data = {"refresh": second["refresh_token"]}
        self.assertEqual(self.client.post(reverse("accounts:logout"), data, format="json").status_code, 400)
        self.assertEqual(self.client.post(reverse("accounts:refresh"), data, format="json").status_code, 200)
