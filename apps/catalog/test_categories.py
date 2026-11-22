from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Category


class CategoryAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("catalog_admin", "catalog-admin@example.com", role=User.Role.ADMIN)
        cls.seller = User.objects.create_user("catalog_seller", "catalog-seller@example.com", role=User.Role.SELLER)

    def setUp(self):
        self.create_url = reverse("catalog:admin-category-create")
        self.list_url = reverse("catalog:category-list")
        self.payload = {
            "name": {"en": "Electronics", "ar": "إلكترونيات"},
            "description": {"en": "Electronic devices"},
        }

    def test_admin_creates_localized_category_with_optional_icon_and_duplicate_name(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.create_url, self.payload | {"is_active": False}, format="json", HTTP_ACCEPT_LANGUAGE="ar-EG"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, {
            "id": response.data["id"], "name": "إلكترونيات", "description": "Electronic devices",
            "icon_url": None, "is_active": True,
        })
        self.assertIn("Accept-Language", response["Vary"])
        self.assertEqual(self.client.post(self.create_url, self.payload, format="json").status_code, 201)
        self.assertEqual(Category.objects.count(), 2)

    def test_create_validates_translations_and_optional_url(self):
        self.client.force_authenticate(self.admin)
        for field, value in (
            ("name", "Electronics"),
            ("name", {"ar": "إلكترونيات"}),
            ("description", {"en": " "}),
            ("name", {"en": "Electronics", "fr": "Électronique"}),
            ("icon_url", "icons/electronics.png"),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.post(self.create_url, self.payload | {field: value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(Category.objects.exists())

    def test_public_list_paginates_active_categories_and_localizes_detail(self):
        first = Category.objects.create(**self.payload)
        Category.objects.create(name={"en": "Hidden"}, description={"en": "Hidden"}, is_active=False)
        Category.objects.create(name={"en": "Books"}, description={"en": "Books"})

        response = self.client.get(self.list_url, {"page": 1, "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual([row["id"] for row in response.data["results"]], [first.id])
        self.assertIn("page=2", response.data["next"])
        self.assertIsNone(response.data["previous"])

        detail_url = reverse("catalog:category-detail", args=[first.id])
        detail = self.client.get(detail_url, HTTP_ACCEPT_LANGUAGE="en;q=0.4, ar-EG;q=0.9")
        self.assertEqual(detail.data["name"], "إلكترونيات")
        self.assertEqual(detail.data["description"], "Electronic devices")
        self.assertEqual(self.client.get(detail_url, HTTP_ACCEPT_LANGUAGE="fr").data["name"], "Electronics")

    def test_admin_soft_deletes_and_restores_category(self):
        category = Category.objects.create(**self.payload)
        admin_url = reverse("catalog:admin-category-detail", args=[category.id])
        public_url = reverse("catalog:category-detail", args=[category.id])
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(admin_url).status_code, 204)
        category.refresh_from_db()
        self.assertFalse(category.is_active)
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertEqual(self.client.get(self.list_url).data["count"], 0)

        response = self.client.patch(admin_url, {
            "is_active": True, "icon_url": "https://example.com/categories/electronics.png",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], category.id)
        self.assertTrue(response.data["is_active"])
        self.assertEqual(self.client.get(public_url).data["name"], "Electronics")

    def test_only_admin_can_write_and_only_documented_methods_are_exposed(self):
        category = Category.objects.create(**self.payload)
        admin_url = reverse("catalog:admin-category-detail", args=[category.id])
        self.assertEqual(self.client.post(self.create_url, self.payload, format="json").status_code, 401)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post(self.create_url, self.payload, format="json").status_code, 403)
        self.assertEqual(self.client.patch(admin_url, {"is_active": False}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(admin_url).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.put(admin_url, self.payload, format="json").status_code, 405)
        missing_url = reverse("catalog:admin-category-detail", args=[category.id + 1])
        self.assertEqual(self.client.patch(missing_url, {"is_active": True}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(missing_url).status_code, 404)
