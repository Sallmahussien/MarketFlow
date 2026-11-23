from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Address
from apps.carts.services import add_item
from apps.carts.tests import make_product, make_shop
from apps.orders.checkout import checkout
from apps.orders.models import Order
from apps.orders.tests import catalog_product, customer_with_address
from apps.payments.callbacks import receive_callback
from apps.payments.gateway import gateway
from apps.payments.models import MockSession


def paid_order():
    customer, address = customer_with_address("fulfillment-buyer")
    first = catalog_product()
    second = make_product(make_shop("second-seller", "8.00"), first.category, "30.00")
    add_item(customer, first.pk, 2)
    add_item(customer, second.pk, 1)
    checkout(customer, address.pk, lambda path: path)
    session = MockSession.objects.get()
    session.outcome = "SUCCESS"
    receive_callback(*gateway.signed_result(session))
    order = Order.objects.get(pk=session.order_reference)
    return order, first, second


@override_settings(MOCK_PAYMENT_SECRET="test-only-secret")
class FulfillmentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order, cls.first, cls.second = paid_order()
        cls.fulfillment = cls.order.fulfillments.get(shop=cls.first.shop)
        cls.other_fulfillment = cls.order.fulfillments.get(shop=cls.second.shop)

    def setUp(self):
        self.client.force_authenticate(self.first.shop.user)
        self.list_url = reverse("fulfillments:list")
        self.detail_url = reverse("fulfillments:detail", args=[self.fulfillment.pk])

    def update(self, status=None, **fields):
        if status:
            fields["status"] = status
        return self.client.patch(self.detail_url, fields, format="json")

    def test_seller_list_and_detail_are_scoped_to_their_shop(self):
        response = self.client.get(self.list_url, {"status": "PENDING", "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.fulfillment.pk)
        self.assertEqual(self.client.get(self.list_url, {"status": "CANCELED"}).data["count"], 0)
        self.assertEqual(self.client.get(self.list_url, {"status": "INVALID"}).status_code, 400)
        Address.objects.filter(user=self.order.user).update(city="Alexandria")
        response = self.client.get(self.detail_url, HTTP_ACCEPT_LANGUAGE="ar-EG")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_address"]["city"], "Cairo")
        self.assertIn("Accept-Language", response.headers["Vary"])
        item, = response.data["items"]
        self.assertEqual(item, {
            "order_item_id": self.fulfillment.items.get().pk, "product_id": self.first.pk,
            "title": "لوحة مفاتيح", "quantity": 2, "unit_price": "20.00",
        })
        other_url = reverse("fulfillments:detail", args=[self.other_fulfillment.pk])
        self.assertEqual(self.client.get(other_url).status_code, 404)
        self.assertEqual(self.client.patch(other_url, {"status": "PREPARING"}, format="json").status_code, 404)
        for user, expected in ((self.order.user, 403), (None, 401)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.list_url).status_code, expected)
            self.assertEqual(self.client.get(self.detail_url).status_code, expected)
            self.assertEqual(self.update("PREPARING").status_code, expected)

    def test_transitions_tracking_and_customer_order_state(self):
        for status in ("SHIPPED", "CANCELED", "INVALID"):
            self.assertEqual(self.update(status).status_code, 400)
        self.assertEqual(self.update(shop_id=self.second.shop_id).status_code, 400)
        response = self.update("PREPARING", carrier_name="Bosta", tracking_number="TRK-1")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("delivery_address", response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.update("SHIPPED").status_code, 200)
        self.assertEqual(self.update(tracking_number="TRK-2").data["tracking_number"], "TRK-2")
        self.assertEqual(self.update("PREPARING").status_code, 400)
        self.assertEqual(self.update("DELIVERED").status_code, 200)
        self.assertEqual(self.update("DELIVERED").status_code, 200)
        self.assertEqual(self.update(tracking_number="TRK-3").status_code, 400)

        self.client.force_authenticate(self.order.user)
        order_url = reverse("orders:detail", args=[self.order.pk])
        detail = self.client.get(order_url).data
        self.assertEqual((detail["status"], detail["payment_status"]), ("PARTIALLY_FULFILLED", "SUCCESS"))
        self.assertEqual({entry["status"] for entry in detail["fulfillments"]}, {"DELIVERED", "PENDING"})

        self.client.force_authenticate(self.second.shop.user)
        second_url = reverse("fulfillments:detail", args=[self.other_fulfillment.pk])
        for status in ("PREPARING", "SHIPPED", "DELIVERED"):
            self.assertEqual(self.client.patch(second_url, {"status": status}, format="json").status_code, 200)
        self.client.force_authenticate(self.order.user)
        self.assertEqual(self.client.get(order_url).data["status"], "COMPLETED")
        response = self.client.get(reverse("orders:list"), {"status": "COMPLETED"})
        self.assertEqual(response.data["count"], 1)


@override_settings(MOCK_PAYMENT_SECRET="test-only-secret")
class FulfillmentConcurrencyTests(TransactionTestCase):
    def test_concurrent_deliveries_complete_the_shared_order(self):
        order, first, second = paid_order()
        order.fulfillments.update(status="SHIPPED")
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PARTIALLY_FULFILLED)
        start = Barrier(2)

        def deliver(product):
            try:
                url = reverse("fulfillments:detail", args=[order.fulfillments.get(shop_id=product.shop_id).pk])
                client = APIClient()
                client.force_authenticate(product.shop.user)
                start.wait(timeout=10)
                return client.patch(url, {"status": "DELIVERED"}, format="json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(deliver, (first, second)))
        self.assertEqual(results, [200, 200])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
