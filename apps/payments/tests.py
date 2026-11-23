from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.carts.models import Cart
from apps.orders.models import Order

from .models import Payment, PaymentEvent


class AdminPaymentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("payments-admin", "payments-admin@example.com", role=User.Role.ADMIN)
        cls.customer = User.objects.create_user("payments-buyer", "payments-buyer@example.com")
        cls.seller = User.objects.create_user("payments-seller", "payments-seller@example.com", role=User.Role.SELLER)
        cls.now = timezone.now()

        def payment(state, transaction_id=None, order_status=Order.Status.PENDING_PAYMENT):
            cart = Cart.objects.create(user=cls.customer, is_active=False)
            order = Order.objects.create(
                cart=cart, user=cls.customer, status=order_status, address_snapshot={}, shipping_by_shop={},
                subtotal="20.00", shipping_total="5.00", total_amount="25.00", expires_at=cls.now + timedelta(minutes=30),
            )
            return Payment.objects.create(
                order=order, state=state, transaction_id=transaction_id, expires_at=order.expires_at - timedelta(minutes=1),
            )

        cls.pending = [payment(state).pk for state in Payment.PENDING_STATES]
        cls.failed = payment(Payment.State.FAILED, "failed")
        cls.expired = payment(Payment.State.EXPIRED, order_status=Order.Status.EXPIRED)
        cls.normal = payment(Payment.State.SUCCESS, "normal", Order.Status.COMPLETED)
        cls.late = payment(Payment.State.SUCCESS, "late", Order.Status.EXPIRED)
        cls.additional = payment(Payment.State.SUCCESS, "additional", Order.Status.CONFIRMED)
        Payment.objects.update(created_at=cls.now)
        for attempt, code in ((cls.normal, ""), (cls.late, "late_success"), (cls.additional, "additional_charge")):
            for seq in range(2):
                PaymentEvent.objects.create(
                    payment=attempt, event_id=f"{attempt.pk}-{seq}", transaction_id=attempt.transaction_id,
                    outcome="SUCCESS", amount="25.00", currency="EGP", attention_reason=code,
                )

    def setUp(self):
        self.url = reverse("payments:admin-list")
        self.client.force_authenticate(self.admin)

    def test_overview_is_newest_first_paginated_and_hides_session_data(self):
        response = self.client.get(self.url, {"page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 8)
        self.assertIsNotNone(response.data["next"])
        self.assertEqual(response.data["results"], [{
            "id": self.additional.pk, "order_id": self.additional.order_id, "transaction_id": "additional",
            "status": "SUCCESS", "requires_attention": True, "reason": "ADDITIONAL_CHARGE",
        }])

    def test_filters_match_the_display_status_and_verified_attention_flags(self):
        flagged = self.client.get(self.url, {"status": "SUCCESS", "requires_attention": "true"}).data["results"]
        self.assertEqual([(row["id"], row["reason"]) for row in flagged], [
            (self.additional.pk, "ADDITIONAL_CHARGE"), (self.late.pk, "PAYMENT_AFTER_ORDER_EXPIRATION"),
        ])
        normal, = self.client.get(self.url, {"status": "SUCCESS", "requires_attention": "false"}).data["results"]
        self.assertEqual((normal["id"], normal["requires_attention"], normal["reason"]), (self.normal.pk, False, None))
        pending = self.client.get(self.url, {"status": "PENDING"}).data["results"]
        self.assertEqual([row["id"] for row in pending], self.pending[::-1])
        self.assertTrue(all(row["status"] == "PENDING" and row["transaction_id"] is None for row in pending))
        failed, = self.client.get(self.url, {"status": "FAILED"}).data["results"]
        self.assertEqual((failed["id"], failed["status"]), (self.failed.pk, "FAILED"))
        results = self.client.get(self.url).data["results"]
        expired = next(row for row in results if row["id"] == self.expired.pk)
        self.assertEqual((expired["status"], expired["requires_attention"]), ("EXPIRED", False))

    def test_endpoint_requires_admin_and_rejects_invalid_filters_and_writes(self):
        for params in ({"status": "OPEN"}, {"requires_attention": "yes"}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}, format="json").status_code, 405)
        for user, expected in ((self.customer, 403), (self.seller, 403), (None, 401)):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url).status_code, expected)
