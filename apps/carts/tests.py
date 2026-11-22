from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.shops.models import Shop

from .models import Cart, CartItem
from .services import add_item


def make_shop(username, fee):
    seller = User.objects.create_user(username, f"{username}@example.com", role=User.Role.SELLER)
    return Shop.objects.create(
        user=seller, name={"en": username}, description={"en": "Shop"},
        shipping_fee=fee, status=Shop.Status.APPROVED, is_active=True,
    )


def make_product(shop, category, price="20.00"):
    return Product.objects.create(
        shop=shop, category=category, title={"en": "Keyboard", "ar": "لوحة مفاتيح"},
        description={"en": "Example"}, price=price, stock=10, is_published=True,
    )


class CartAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user("buyer", "buyer@example.com")
        cls.other = User.objects.create_user("other", "other@example.com")
        cls.shop = make_shop("seller", "5.00")
        cls.other_shop = make_shop("other-seller", "7.00")
        cls.category = Category.objects.create(name={"en": "Electronics"}, description={"en": "Devices"})
        cls.product = make_product(cls.shop, cls.category)
        cls.second = make_product(cls.shop, cls.category, "10.00")
        cls.third = make_product(cls.other_shop, cls.category, "30.00")

    def setUp(self):
        self.cart_url = reverse("carts:cart")
        self.client.force_authenticate(self.customer)

    def item_url(self, item):
        return reverse("carts:item", args=[item["id"]])

    def add(self, product, count):
        response = self.client.post(self.cart_url, {"product_id": product.pk, "count": count}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_cart_lifecycle_and_stock_is_not_reserved(self):
        empty = self.client.get(self.cart_url).data
        self.assertEqual(empty["total"], "0.00")
        cart = self.add(self.product, 2)
        cart = self.add(self.product, 3)
        self.assertEqual(cart["id"], empty["id"])
        self.assertEqual((cart["item_count"], cart["total_count"]), (1, 5))
        self.assertEqual(cart["total"], "105.00")
        item_url = self.item_url(cart["items"][0])
        response = self.client.patch(item_url, {"count": 4}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["count"], 4)
        removed = self.client.delete(item_url)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.data["items"], [])
        self.add(self.product, 1)
        self.assertEqual(self.client.delete(self.cart_url).status_code, 204)
        self.assertEqual(self.client.get(self.cart_url).data, empty)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_totals_use_current_prices_and_available_lines_with_one_fee_per_shop(self):
        self.add(self.product, 2)
        self.add(self.second, 1)
        cart = self.add(self.third, 2)
        self.assertEqual((cart["sub_total"], cart["total_shipping"], cart["total"]), ("110.00", "12.00", "122.00"))
        Product.objects.filter(pk=self.product.pk).update(price="25.00")
        Product.objects.filter(pk=self.third.pk).update(stock=1)
        response = self.client.get(self.cart_url, HTTP_ACCEPT_LANGUAGE="ar-EG")
        cart = response.data
        self.assertEqual((cart["item_count"], cart["total_count"]), (3, 5))
        self.assertEqual((cart["sub_total"], cart["total_shipping"], cart["total"]), ("60.00", "5.00", "65.00"))
        self.assertEqual(cart["items"][0]["title"], "لوحة مفاتيح")
        self.assertFalse(cart["items"][2]["is_available"])
        self.assertEqual(cart["items"][2]["line_total"], "60.00")
        self.assertEqual(self.client.delete(self.item_url(cart["items"][2])).status_code, 200)

    def test_validation_blocks_invalid_missing_and_unavailable_products(self):
        cart = self.add(self.product, 8)
        item_url = self.item_url(cart["items"][0])
        for count, expected in ((0, 400), (3, 400)):
            response = self.client.post(
                self.cart_url, {"product_id": self.product.pk, "count": count}, format="json"
            )
            self.assertEqual(response.status_code, expected)
        self.assertEqual(self.client.patch(item_url, {"count": 11}, format="json").status_code, 400)
        self.assertEqual(
            self.client.post(self.cart_url, {"product_id": self.product.pk + 1000, "count": 1}, format="json").status_code,
            404,
        )
        Shop.objects.filter(pk=self.shop.pk).update(is_active=False)
        self.assertEqual(self.client.patch(item_url, {"count": 1}, format="json").status_code, 400)
        self.assertFalse(self.client.get(self.cart_url).data["items"][0]["is_available"])

    def test_roles_and_item_ownership(self):
        cart = self.add(self.product, 1)
        foreign_url = self.item_url(cart["items"][0])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.cart_url).data["items"], [])
        self.assertEqual(self.client.patch(foreign_url, {"count": 2}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(foreign_url).status_code, 404)
        self.client.force_authenticate(self.shop.user)
        self.assertEqual(self.client.get(self.cart_url).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.cart_url).status_code, 401)


class CartConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_first_adds_share_one_cart_and_increment_one_line(self):
        customer = User.objects.create_user("concurrent-buyer", "concurrent@example.com")
        shop = make_shop("concurrent-seller", "0.00")
        category = Category.objects.create(name={"en": "Category"}, description={"en": "Category"})
        product = make_product(shop, category)
        start = Barrier(2)

        def add_concurrently():
            try:
                start.wait(timeout=10)
                add_item(customer, product.pk, 1)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            workers = [executor.submit(add_concurrently) for _ in range(2)]
            for worker in workers:
                worker.result(timeout=15)

        cart = Cart.objects.get(user=customer, is_active=True)
        self.assertEqual(CartItem.objects.get(cart=cart, product=product).quantity, 2)
