from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Address, User


class AddressAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user("address-customer", "address-customer@example.com")
        cls.other = User.objects.create_user("other-customer", "other-customer@example.com")
        cls.seller = User.objects.create_user(
            "address-seller", "address-seller@example.com", role=User.Role.SELLER
        )
        cls.admin = User.objects.create_user(
            "address-admin", "address-admin@example.com", role=User.Role.ADMIN
        )
        cls.payload = {
            "first_name": "Ahmed",
            "last_name": "Ali",
            "phone_number": "01012345678",
            "building": "12B",
            "street_name": "Tahrir Street",
            "apartment": "05",
            "city": "Dokki",
            "governorate": "Giza",
            "postal_code": "00126",
        }

    def setUp(self):
        self.list_url = reverse("addresses:list")

    def detail_url(self, address_id):
        return reverse("addresses:detail", args=[address_id])

    def test_customer_can_create_retrieve_patch_and_delete_own_address(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            self.list_url, self.payload | {"user_id": self.other.pk}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        address_id = response.data["id"]
        self.assertEqual(response.data, self.payload | {"id": address_id})
        self.assertEqual(Address.objects.get(pk=address_id).user_id, self.customer.pk)

        url = self.detail_url(address_id)
        self.assertEqual(self.client.get(url).data, response.data)
        edits = {"apartment": "07", "phone_number": "01098765432"}
        response = self.client.patch(
            url, edits | {"user_id": self.other.pk, "id": address_id + 1}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.payload | edits | {"id": address_id})
        self.assertEqual(Address.objects.get(pk=address_id).user_id, self.customer.pk)
        self.assertEqual(self.client.put(url, self.payload, format="json").status_code, 405)

        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Address.objects.filter(pk=address_id).exists())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_list_is_paginated_and_all_lookups_are_owner_scoped(self):
        first = Address.objects.create(user=self.customer, **self.payload)
        second = Address.objects.create(user=self.customer, **self.payload)
        foreign = Address.objects.create(user=self.other, **self.payload)
        self.client.force_authenticate(self.customer)
        page = self.client.get(self.list_url, {"page": 1, "page_size": 1})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.data["count"], 2)
        self.assertEqual([item["id"] for item in page.data["results"]], [first.pk])
        self.assertIn("page=2", page.data["next"])
        page = self.client.get(self.list_url, {"page": 2, "page_size": 1})
        self.assertEqual([item["id"] for item in page.data["results"]], [second.pk])

        url = self.detail_url(foreign.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"city": "Cairo"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.city, self.payload["city"])

    def test_only_customers_can_access_addresses(self):
        address = Address.objects.create(user=self.customer, **self.payload)
        for actor, expected in ((None, 401), (self.seller, 403), (self.admin, 403)):
            with self.subTest(actor=actor):
                self.client.force_authenticate(actor)
                self.assertEqual(self.client.get(self.list_url).status_code, expected)
                self.assertEqual(self.client.post(self.list_url, self.payload, format="json").status_code, expected)
                self.assertEqual(self.client.get(self.detail_url(address.pk)).status_code, expected)

    def test_invalid_data_returns_field_errors(self):
        self.client.force_authenticate(self.customer)
        incomplete = self.payload.copy()
        incomplete.pop("building")
        response = self.client.post(self.list_url, incomplete, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("building", response.data)

        address = Address.objects.create(user=self.customer, **self.payload)
        response = self.client.patch(
            self.detail_url(address.pk), {"postal_code": "0" * 21}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("postal_code", response.data)
