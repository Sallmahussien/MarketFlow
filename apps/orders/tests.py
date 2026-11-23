import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Address, User
from apps.carts.services import add_item
from apps.carts.tests import make_product, make_shop
from apps.catalog.models import Category, Product
from apps.fulfillments.models import Fulfillment
from apps.payments.callbacks import receive_callback
from apps.payments.gateway import gateway
from apps.payments.models import MockSession, Payment, PaymentEvent
from apps.shops.models import Shop

from .checkout import checkout
from .models import Order
from .reservations import expire_order


def customer_with_address(name):
    user = User.objects.create_user(name, f"{name}@example.com")
    address = Address.objects.create(user=user, first_name=name, last_name="Example", phone_number="010",
                                     building="12", street_name="Main", city="Cairo", governorate="Cairo")
    return user, address


def catalog_product():
    category = Category.objects.create(name={"en": "Electronics"}, description={"en": "Devices"})
    return make_product(make_shop("seller", "5.00"), category)


@override_settings(MOCK_PAYMENT_SECRET="test-only-secret")
class CheckoutAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.address = customer_with_address("buyer")
        cls.product = catalog_product()

    def setUp(self):
        self.client.force_authenticate(self.user)
        self.cart = add_item(self.user, self.product.pk, 2)
        self.url = reverse("checkout:start")
        self.callback_url = reverse("checkout:callback")

    def start(self, address=None):
        return self.client.post(self.url, {"address_id": (address or self.address).pk}, format="json")

    def notify(self, session, **changes):
        body = {
            "event_id": "event", "order_reference": str(session.order_reference),
            "status": "SUCCESS", "amount": str(session.amount), "currency": session.currency,
            "transaction_id": str(session.transaction_id),
        }
        body.update(changes)
        raw = json.dumps(body).encode()
        return self.client.post(self.callback_url, raw, content_type="application/json",
                                HTTP_X_MOCK_SIGNATURE=gateway.signature(raw))

    def test_multishop_checkout_retry_snapshots_and_mock_success(self):
        other = make_product(make_shop("other", "7.00"), self.product.category, "10.00")
        add_item(self.user, other.pk, 1)
        add_item(self.user, make_product(self.product.shop, self.product.category, "15.00").pk, 1)
        first = self.start()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual((first.data["subtotal"], first.data["shipping_total"], first.data["total_amount"]),
                         ("65.00", "12.00", "77.00"))
        order = Order.objects.get()
        self.assertEqual(order.expires_at - order.created_at, timedelta(minutes=30))
        self.assertEqual(Payment.objects.get().expires_at, order.expires_at - timedelta(minutes=1))
        Address.objects.filter(pk=self.address.pk).update(city="Alexandria")
        Product.objects.filter(pk=self.product.pk).update(price="100.00")
        Shop.objects.filter(pk=self.product.shop_id).update(shipping_fee="99.00")
        retry = self.start()
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data, first.data)
        self.assertEqual(order.address_snapshot["city"], "Cairo")
        path = urlsplit(first.data["payment_url"]).path
        browser = APIClient(enforce_csrf_checks=True)
        self.assertContains(browser.get(path), "77.00 EGP")
        csrf = browser.cookies["csrftoken"].value
        self.assertEqual(browser.post(path, {"outcome": "SUCCESS", "csrfmiddlewaretoken": csrf}).status_code, 200)
        self.assertEqual(browser.post(path, {"outcome": "SUCCESS", "csrfmiddlewaretoken": csrf}).status_code, 200)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.product.stock, 8)
        self.assertFalse(order.cart.is_active)
        self.assertEqual(set(map(str, order.fulfillments.values_list("shipping_fee", flat=True))), {"5.00", "7.00"})
        self.assertFalse(order.items.filter(fulfillment=None).exists())
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_cart_frozen_but_readable_and_addresses_and_customer_role_enforced(self):
        self.assertEqual(self.start().status_code, 201)
        cart_url = reverse("carts:cart")
        item_url = reverse("carts:item", args=[self.cart["items"][0]["id"]])
        self.assertEqual(self.client.get(cart_url).status_code, 200)
        self.assertEqual(self.client.post(cart_url, {"product_id": self.product.pk, "count": 1}).status_code, 403)
        self.assertEqual(self.client.patch(item_url, {"count": 1}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(item_url).status_code, 403)
        self.assertEqual(self.client.delete(cart_url).status_code, 403)
        other_user, other_address = customer_with_address("other")
        self.assertEqual(self.start(other_address).status_code, 404)
        self.client.force_authenticate(other_user)
        self.assertEqual(self.start(other_address).status_code, 400)
        self.client.force_authenticate(self.product.shop.user)
        self.assertEqual(self.start().status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.start().status_code, 401)

    def test_restock_preserves_capacity_to_release_reserved_units(self):
        self.start()
        self.client.force_authenticate(self.product.shop.user)
        url = reverse("catalog:product-detail", args=[self.product.pk])
        maximum = 2**31 - 1
        self.assertEqual(self.client.patch(url, {"stock": maximum}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"stock": maximum - 2}, format="json").status_code, 200)
        order = Order.objects.get()
        with patch("django.utils.timezone.now", return_value=order.expires_at):
            call_command("expire_orders", stdout=StringIO())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, maximum)

    def test_one_unavailable_line_aborts_whole_reservation(self):
        other = make_product(self.product.shop, self.product.category)
        add_item(self.user, other.pk, 1)
        Product.objects.filter(pk=other.pk).update(stock=0)
        self.assertEqual(self.start().status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_failed_payment_gets_new_attempt_with_original_deadline(self):
        first = self.start()
        url = urlsplit(first.data["payment_url"])
        browser = APIClient(enforce_csrf_checks=True)
        page = browser.get(url.path, HTTP_HOST=url.netloc)
        self.assertNotContains(page, '<meta name="referrer" content="no-referrer">')
        self.assertEqual(page.headers["Referrer-Policy"], "same-origin")
        csrf_token = browser.cookies["csrftoken"].value
        form = {"outcome": "FAILED", "csrfmiddlewaretoken": csrf_token}
        self.assertEqual(browser.post(url.path, form, HTTP_HOST=url.netloc, HTTP_ORIGIN="null").status_code, 403)
        result = browser.post(url.path, form, HTTP_HOST=url.netloc, HTTP_ORIGIN=f"{url.scheme}://{url.netloc}")
        self.assertContains(result, "Mock payment result: FAILED.")
        order = Order.objects.get()
        with patch("django.utils.timezone.now", return_value=order.created_at + timedelta(minutes=20)):
            retry = self.start()
            self.assertEqual(retry.status_code, 200)
            self.assertNotEqual(first.data["payment_url"], retry.data["payment_url"])
            self.assertEqual(first.data["expires_at"], retry.data["expires_at"])
            second = Payment.objects.latest("pk")
            self.assertEqual(second.expires_at - timezone.now(), timedelta(minutes=9))
        self.assertEqual(self.notify(MockSession.objects.get(reference=second.reference)).status_code, 200)
        self.assertEqual(self.notify(MockSession.objects.first(), event_id="second-charge").status_code, 200)
        self.assertTrue(PaymentEvent.objects.filter(attention_reason="additional_charge").exists())
        self.assertEqual(Fulfillment.objects.count(), 1)

    def test_timeout_recovers_same_gateway_session_without_second_reservation(self):
        create = gateway.create_session

        def lost_response(*args):
            create(*args)
            raise TimeoutError

        with patch.object(gateway, "create_session", side_effect=lost_response):
            self.assertEqual(self.start().status_code, 503)
        self.assertEqual(Payment.objects.get().state, Payment.State.CREATING)
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(MockSession.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_early_session_expiry_replaces_only_the_attempt(self):
        first = self.start()
        order = Order.objects.get()
        short_expiry = order.created_at + timedelta(minutes=5)
        MockSession.objects.update(expires_at=short_expiry)
        with patch("django.utils.timezone.now", return_value=short_expiry):
            retry = self.start()
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data["order_id"], first.data["order_id"])
        self.assertNotEqual(retry.data["payment_id"], first.data["payment_id"])
        self.assertEqual(Payment.objects.first().state, "EXPIRED")
        self.assertEqual(Payment.objects.last().expires_at, order.expires_at - timedelta(minutes=1))

    def test_unknown_charge_blocks_a_new_link_until_gateway_reports_outcome(self):
        first = self.start()
        Payment.objects.update(state=Payment.State.PROCESSING)
        self.assertEqual(self.start().status_code, 503)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(MockSession.objects.count(), 1)
        MockSession.objects.update(outcome="FAILED")
        retry = self.start()
        self.assertEqual(retry.status_code, 200)
        self.assertNotEqual(retry.data["payment_id"], first.data["payment_id"])
        self.assertEqual(retry.data["order_id"], first.data["order_id"])

    def test_gateway_must_be_configured_before_stock_is_reserved(self):
        with override_settings(MOCK_PAYMENT_SECRET=""):
            self.assertEqual(self.start().status_code, 503)
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_expiration_and_late_callback_then_fresh_checkout(self):
        first = self.start()
        session = MockSession.objects.get()
        order = Order.objects.get()
        path = urlsplit(first.data["payment_url"]).path
        with patch("django.utils.timezone.now", return_value=session.expires_at):
            self.assertEqual(self.start().status_code, 403)
            self.assertEqual(self.client.post(path, {"outcome": "SUCCESS"}).status_code, 409)
        with patch("django.utils.timezone.now", return_value=order.expires_at):
            call_command("expire_orders", stdout=StringIO())
            call_command("expire_orders", stdout=StringIO())
            self.assertEqual(self.notify(session).status_code, 200)
            self.assertEqual(self.notify(session).status_code, 200)
            order.refresh_from_db()
            self.product.refresh_from_db()
            self.assertEqual(self.product.stock, 10)
            self.assertEqual(order.status, Order.Status.EXPIRED)
            self.assertTrue(order.cart.is_active)
            self.assertEqual(PaymentEvent.objects.get().attention_reason, "late_success")
            self.assertFalse(Fulfillment.objects.exists())
            fresh = self.start()
            self.assertEqual(fresh.status_code, 201)
            self.assertNotEqual(fresh.data["order_id"], order.pk)

    def test_due_order_releases_on_invalid_cart_edit_without_worker(self):
        self.start()
        order = Order.objects.get()
        with patch("django.utils.timezone.now", return_value=order.expires_at):
            add_url = reverse("carts:cart")
            self.assertEqual(self.client.post(add_url, {"product_id": self.product.pk, "count": 100}).status_code, 400)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((order.status, self.product.stock), ("EXPIRED", 10))
        self.assertEqual(self.client.delete(add_url).status_code, 204)

    def test_callback_authentication_validation_and_duplicate_events(self):
        self.start()
        session = MockSession.objects.get()
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.callback_url, {}, format="json").status_code, 403)
        for changes in ({"amount": "0.01"}, {"currency": "USD"}, {"order_reference": "9999"},
                        {"transaction_id": "bad"}, {"status": "UNKNOWN"}):
            self.assertEqual(self.notify(session, **changes).status_code, 400)
        self.assertFalse(PaymentEvent.objects.exists())
        self.assertEqual(self.notify(session).status_code, 200)
        self.assertEqual(self.notify(session, status="FAILED").status_code, 400)
        self.assertEqual(self.notify(session, event_id="another-event").status_code, 200)
        self.assertEqual(self.notify(session, event_id="old-failure", status="FAILED").status_code, 200)
        self.assertFalse(PaymentEvent.objects.exclude(attention_reason="").exists())
        self.assertEqual(Payment.objects.get().state, "SUCCESS")
        self.assertEqual(Fulfillment.objects.count(), 1)


@override_settings(MOCK_PAYMENT_SECRET="test-only-secret")
class CheckoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user, self.address = customer_with_address("buyer")
        self.product = catalog_product()
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        add_item(self.user, self.product.pk, 1)

    def start(self, user, address):
        return checkout(user, address.pk, lambda path: "https://example.com" + path)

    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, op) for op in operations]
            return [future.result(timeout=15) for future in futures]

    def test_two_checkouts_share_order_attempt_and_link(self):
        def start():
            return self.start(self.user, self.address)
        results = self.race(start, start)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual({result[1] for result in results}, {True, False})
        self.assertEqual((Order.objects.count(), Payment.objects.count(), MockSession.objects.count()), (1, 1, 1))

    def test_competing_customers_cannot_reserve_last_unit_twice(self):
        other, address = customer_with_address("other")
        add_item(other, self.product.pk, 1)

        def attempt(user, address):
            try:
                self.start(user, address)
                return True
            except ValidationError:
                return False
        self.assertCountEqual(self.race(lambda: attempt(self.user, self.address), lambda: attempt(other, address)),
                              [True, False])
        self.product.refresh_from_db()
        self.assertEqual((Order.objects.count(), self.product.stock), (1, 0))

    def test_callback_racing_expiry_at_deadline_releases_once(self):
        self.start(self.user, self.address)
        order = Order.objects.get()
        session = MockSession.objects.get()
        session.outcome = "SUCCESS"
        body, signature = gateway.signed_result(session)
        with patch("django.utils.timezone.now", return_value=order.expires_at):
            self.race(lambda: expire_order(order.cart_id, order.pk), lambda: receive_callback(body, signature))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((order.status, self.product.stock), ("EXPIRED", 1))
        self.assertEqual(PaymentEvent.objects.get().attention_reason, "late_success")
        self.assertFalse(Fulfillment.objects.exists())
