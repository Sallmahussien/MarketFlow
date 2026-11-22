from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.shops.models import Shop

from .models import Category, Product


class ProductAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name={"en": "Electronics"}, description={"en": "Devices"})
        cls.inactive_category = Category.objects.create(
            name={"en": "Hidden"}, description={"en": "Hidden"}, is_active=False
        )
        cls.seller = User.objects.create_user("product-seller", "product-seller@example.com", role=User.Role.SELLER)
        cls.other = User.objects.create_user("other-seller", "other-seller@example.com", role=User.Role.SELLER)
        cls.shop = Shop.objects.create(
            user=cls.seller, name={"en": "Seller"}, description={"en": "Seller"}, shipping_fee=0,
            status=Shop.Status.APPROVED, is_active=True,
        )
        cls.other_shop = Shop.objects.create(
            user=cls.other, name={"en": "Other"}, description={"en": "Other"}, shipping_fee=0,
            status=Shop.Status.APPROVED, is_active=True,
        )

    def setUp(self):
        self.public_url = reverse("catalog:product-list")
        self.seller_url = reverse("catalog:seller-product-list")
        self.payload = {
            "title": {"en": "iPhone", "ar": "آيفون"},
            "description": {"en": "Apple smartphone", "ar": ""},
            "price": "35000.00", "stock": 10, "category_id": self.category.pk,
        }

    def create_draft(self, **overrides):
        self.client.force_authenticate(self.seller)
        response = self.client.post(self.public_url, self.payload | overrides, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def detail(self, product):
        return reverse("catalog:product-detail", args=[product["id"]])

    def image_detail(self, product, image):
        return reverse("catalog:product-image-detail", args=[product["id"], image["id"]])

    def add_image(self, product, path):
        url = reverse("catalog:product-image-create", args=[product["id"]])
        response = self.client.post(url, {"image_path": path}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    @override_settings(PRODUCT_IMAGE_BASE_URL="https://cdn.example.com/media/")
    def test_draft_publication_and_image_lifecycle(self):
        draft = self.create_draft(shop_id=self.other_shop.pk, is_published=True)
        self.assertEqual(draft["shop_id"], self.shop.pk)
        self.assertFalse(draft["is_published"])
        self.assertEqual(draft["images"], [])
        detail_url = self.detail(draft)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.assertEqual(self.client.patch(detail_url, {"is_published": True}, format="json").status_code, 400)

        first = self.add_image(draft, "media/products/front view.jpg")
        second = self.add_image(draft, "products/back.jpg")
        third = self.add_image(draft, "products/side.jpg")
        self.assertTrue(first["is_primary"])
        self.assertFalse(second["is_primary"])
        self.assertFalse(third["is_primary"])
        response = self.client.patch(self.image_detail(draft, second), {"is_primary": False}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(self.image_detail(draft, second), {"is_primary": True}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_primary"])

        published = self.client.patch(detail_url, {"is_published": True}, format="json")
        self.assertEqual(published.status_code, 200)
        self.assertEqual([row["id"] for row in published.data["images"] if row["is_primary"]], [second["id"]])
        expected_url = "https://cdn.example.com/media/products/front%20view.jpg"
        self.assertEqual(published.data["images"][0]["image_path"], expected_url)
        self.assertEqual(self.client.get(self.seller_url).data["results"][0]["images"][0]["image_path"], expected_url)
        public = self.client.get(detail_url)
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.data["images"][0]["image_path"], expected_url)

        self.assertEqual(self.client.delete(self.image_detail(draft, second)).status_code, 204)
        remaining = self.client.get(detail_url).data["images"]
        self.assertEqual([row["id"] for row in remaining if row["is_primary"]], [first["id"]])
        self.assertEqual(self.client.delete(self.image_detail(draft, third)).status_code, 204)
        self.assertEqual(self.client.delete(self.image_detail(draft, first)).status_code, 204)
        self.assertFalse(Product.objects.get(pk=draft["id"]).is_published)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

    @override_settings(PRODUCT_IMAGE_BASE_URL="https://cdn.example.com")
    def test_seller_permissions_and_owner_scope(self):
        self.assertEqual(self.client.post(self.public_url, self.payload, format="json").status_code, 401)
        draft = self.create_draft(stock=0)
        image = self.add_image(draft, "products/photo.jpg")
        seller_detail = reverse("catalog:seller-product-detail", args=[draft["id"]])
        detail = self.client.get(seller_detail)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["images"][0]["image_path"], "https://cdn.example.com/products/photo.jpg")
        self.assertEqual(self.client.get(self.seller_url).data["count"], 1)
        self.client.force_authenticate(self.other)
        other_draft = self.client.post(self.public_url, self.payload, format="json").data
        wrong_parent = self.image_detail(other_draft, image)
        self.assertEqual(self.client.get(seller_detail).status_code, 404)
        self.assertEqual(self.client.patch(self.detail(draft), {"stock": 1}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(self.image_detail(draft, image)).status_code, 404)
        self.assertEqual(self.client.patch(wrong_parent, {"is_primary": True}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(wrong_parent).status_code, 404)
        self.assertEqual([row["id"] for row in self.client.get(self.seller_url).data["results"]], [other_draft["id"]])
        Shop.objects.filter(pk=self.other_shop.pk).update(status=Shop.Status.PENDING)
        self.assertEqual(self.client.get(self.seller_url).status_code, 403)
        self.assertEqual(self.client.post(self.public_url, self.payload, format="json").status_code, 403)

    def test_product_and_image_validation(self):
        self.client.force_authenticate(self.seller)
        for field, value in (
            ("title", "iPhone"), ("description", {"en": ""}), ("price", "0.00"),
            ("stock", -1), ("category_id", self.inactive_category.pk), ("category_id", 999999),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.post(self.public_url, self.payload | {field: value}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        draft = self.create_draft()
        response = self.client.patch(self.detail(draft), {"category_id": self.inactive_category.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        image_url = reverse("catalog:product-image-create", args=[draft["id"]])
        for path in ("../front.jpg", "https://example.com/front.jpg", "/front.jpg"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(image_url, {"image_path": path}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(self.detail(draft)).status_code, 405)

    def test_public_visibility_uses_shop_category_stock_and_publication(self):
        draft = self.create_draft()
        self.add_image(draft, "products/visible.jpg")
        url = self.detail(draft)
        self.assertEqual(self.client.patch(url, {"is_published": True}, format="json").status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 200)
        for model, pk, field, hidden, visible in (
            (Shop, self.shop.pk, "is_active", False, True),
            (Shop, self.shop.pk, "status", Shop.Status.REJECTED, Shop.Status.APPROVED),
            (Category, self.category.pk, "is_active", False, True),
            (Product, draft["id"], "stock", 0, 10),
            (Product, draft["id"], "is_published", False, True),
        ):
            with self.subTest(field=field):
                model.objects.filter(pk=pk).update(**{field: hidden})
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.get(self.public_url).data["count"], 0)
                model.objects.filter(pk=pk).update(**{field: visible})

    def test_public_filters_search_and_ordering(self):
        first = self.create_draft()
        self.add_image(first, "products/first.jpg")
        self.client.patch(self.detail(first), {"is_published": True}, format="json")
        second = self.create_draft(title={"en": "Cable"}, description={"en": "USB cable"}, price="10.00")
        self.add_image(second, "products/second.jpg")
        self.client.patch(self.detail(second), {"is_published": True}, format="json")
        self.client.force_authenticate(None)
        response = self.client.get(self.public_url, {
            "shop_id": self.shop.pk, "category_id": self.category.pk, "min_price": "10.00",
            "max_price": "35000.00", "ordering": "-price", "page_size": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["id"], first["id"])
        self.assertIn("page=2", response.data["next"])
        self.assertEqual(self.client.get(self.public_url).data["results"][0]["id"], second["id"])
        self.assertEqual(self.client.get(self.public_url, {
            "shop_id": self.other_shop.pk, "category_id": self.category.pk
        }).data["count"], 0)
        self.assertEqual(self.client.get(self.public_url, {"min_price": "20.00", "max_price": "10.00"}).status_code, 400)
        self.assertEqual(self.client.get(self.public_url, {"ordering": "no_such_field"}).status_code, 400)

        for search, expected in (("آيفون", first), ("smartphone", first), ("Cable", second)):
            with self.subTest(search=search):
                localized = self.client.get(self.public_url, {"search": search}, HTTP_ACCEPT_LANGUAGE="ar-EG")
                self.assertEqual(localized.status_code, 200)
                self.assertEqual([row["id"] for row in localized.data["results"]], [expected["id"]])
        sorted_products = self.client.get(self.public_url, {"ordering": "title"}, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual([row["id"] for row in sorted_products.data["results"]], [second["id"], first["id"]])
