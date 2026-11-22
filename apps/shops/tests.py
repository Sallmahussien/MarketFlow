from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Shop


class ShopAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user("seller", "seller@example.com", role=User.Role.SELLER)
        cls.other_seller = User.objects.create_user("other", "other@example.com", role=User.Role.SELLER)
        cls.customer = User.objects.create_user("customer", "customer@example.com")
        cls.admin = User.objects.create_user("admin", "admin@example.com", role=User.Role.ADMIN)

    def setUp(self):
        self.list_url = reverse("shops:list-create")
        self.own_url = reverse("shops:own")
        self.admin_list_url = reverse("shops:admin-list")
        self.payload = {
            "name": {"en": "Tech Store", "ar": "متجر التقنية"},
            "description": {"en": "Electronics", "ar": ""},
            "logo_url": "shops/logos/tech-store.png",
            "shipping_fee": "50.00",
        }

    def create_shop(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(self.list_url, self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_seller_submits_once_and_can_read_only_their_own_shop(self):
        self.assertEqual(self.client.post(self.list_url, self.payload, format="json").status_code, 401)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(self.list_url, self.payload, format="json").status_code, 403)

        created = self.create_shop()
        self.assertEqual(created, {
            "id": created["id"], "name": "Tech Store", "description": "Electronics",
            "logo_url": self.payload["logo_url"], "shipping_fee": "50.00", "status": "PENDING",
            "is_active": False,
        })
        self.assertEqual(self.client.post(self.list_url, self.payload, format="json").status_code, 400)
        self.assertEqual(Shop.objects.count(), 1)
        self.assertIsNone(self.client.get(self.own_url).data["rejection_reason"])
        self.assertEqual(self.client.patch(self.own_url, {}, format="json").status_code, 400)
        self.client.force_authenticate(self.other_seller)
        self.assertEqual(self.client.get(self.own_url).status_code, 404)
        self.assertEqual(self.client.patch(self.own_url, {"is_active": True}, format="json").status_code, 404)

    def test_invalid_application_fields_return_400(self):
        self.client.force_authenticate(self.seller)
        for field, value in (
            ("name", "Tech Store"), ("name", {"ar": "متجر"}), ("name", {"en": " "}),
            ("name", {"en": "Store", "fr": "Boutique"}), ("description", {"en": 12}),
            ("shipping_fee", "-1.00"),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.post(self.list_url, self.payload | {field: value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_admin_permissions_filters_and_detail(self):
        shop = self.create_shop()
        url = reverse("shops:admin-detail", args=[shop["id"]])
        self.assertEqual(self.client.get(self.admin_list_url).status_code, 403)
        self.assertEqual(self.client.patch(url, {"status": "APPROVED"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.admin_list_url, {"status": "PENDING"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["user_id"], self.seller.id)
        self.assertEqual(self.client.get(self.admin_list_url, {"status": "APPROVED"}).data, [])
        self.assertEqual(self.client.get(self.admin_list_url, {"status": "UNKNOWN"}).status_code, 400)
        detail = self.client.get(url).data
        self.assertEqual(set(detail["user"]), {"id", "username", "email", "first_name", "last_name", "phone"})
        self.assertEqual(detail["user"]["email"], self.seller.email)
        self.assertEqual(detail["shop"]["status"], "PENDING")
        missing = reverse("shops:admin-detail", args=[shop["id"] + 1])
        self.assertEqual(self.client.patch(missing, {"status": "APPROVED"}, format="json").status_code, 404)

    def test_rejected_shop_requires_a_meaningful_edit_to_resubmit(self):
        shop = self.create_shop()
        url = reverse("shops:admin-detail", args=[shop["id"]])
        self.client.force_authenticate(self.admin)
        for body in ({"status": "PENDING"}, {"status": "REJECTED", "rejection_reason": " "}, {}):
            self.assertEqual(self.client.patch(url, body, format="json").status_code, 400)
        rejected = self.client.patch(
            url, {"status": "REJECTED", "rejection_reason": "Add detail."}, format="json"
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.data["status"], "REJECTED")
        self.assertEqual(self.client.patch(url, {"status": "APPROVED"}, format="json").status_code, 400)
        self.client.force_authenticate(self.seller)
        unchanged = self.client.patch(
            self.own_url, {"is_active": True, "shipping_fee": "50.00"}, format="json"
        )
        self.assertEqual(unchanged.data["status"], "REJECTED")
        self.assertEqual(unchanged.data["rejection_reason"], "Add detail.")
        resubmitted = self.client.patch(
            self.own_url, {"description": {"en": "Electronics and accessories"}}, format="json"
        )
        self.assertEqual(resubmitted.data["status"], "PENDING")
        self.assertIsNone(resubmitted.data["rejection_reason"])
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.role, User.Role.SELLER)

    def test_only_approved_active_shops_are_public_and_localized(self):
        shop = self.create_shop()
        public_url = reverse("shops:public-detail", args=[shop["id"]])
        admin_url = reverse("shops:admin-detail", args=[shop["id"]])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url).data, [])
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.client.force_authenticate(self.admin)
        approved = self.client.patch(admin_url, {"status": "APPROVED"}, format="json")
        self.assertEqual(approved.data["status"], "APPROVED")
        self.assertFalse(approved.data["is_active"])
        self.assertEqual(self.client.get(public_url).status_code, 404)

        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.patch(self.own_url, {"is_active": True}, format="json").status_code, 200)
        self.client.force_authenticate(None)
        response = self.client.get(public_url, HTTP_ACCEPT_LANGUAGE="en;q=0.4, ar-EG;q=0.9")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "متجر التقنية")
        self.assertEqual(response.data["description"], "Electronics")
        self.assertNotIn("status", response.data)
        self.assertIn("Accept-Language", response["Vary"])
        self.assertEqual(self.client.get(self.list_url, HTTP_ACCEPT_LANGUAGE="ar;q=0").data[0]["name"], "Tech Store")
