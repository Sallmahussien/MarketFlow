# MarketFlow
Multi-Vendor Marketplace Backend

## Mock checkout

Set `PRODUCT_IMAGE_BASE_URL` and a private `MOCK_PAYMENT_SECRET` in the environment or Compose `.env` file. For example, generate a signing secret with `openssl rand -hex 32`. Run `docker compose up -d --build --wait` to apply migrations and start the web service and reservation expiry worker.

1. Sign in as a customer, add items to the cart, and create a delivery address.
2. Send `POST /api/v1/checkout/` with the customer bearer token and JSON such as `{"address_id": 12}`. A new order returns HTTP 201. Repeating checkout for a pending order returns HTTP 200 and preserves its original address, amounts, and deadline. The response includes the order and payment IDs, amount breakdown, `payment_url`, `payment_url_expires_at`, and order `expires_at`.
3. Open the returned URL in a browser and choose a simulated success or failure. A success confirms the order, deactivates the cart, and creates one fulfillment per shop. After a failure, repeat checkout to get a new attempt on the same order.
4. A reservation lasts 30 minutes. The mock accepts payment submissions until one minute before the reservation deadline. The cart rejects edits while reserved. The expiry worker checks every 15 seconds, and cart writes and checkout also release an overdue reservation. Run `python manage.py expire_orders` for a single sweep outside Compose.

### Callback contract

`POST /api/v1/checkout/callback/` accepts JSON with `event_id`, `order_reference`, `transaction_id`, `status` (`SUCCESS` or `FAILED`), `amount`, and `currency` (`EGP`). The mock assigns one transaction UUID per session. Send `X-Mock-Signature` containing the lowercase hexadecimal HMAC-SHA256 of the exact request bytes using `MOCK_PAYMENT_SECRET`. The mock form uses the same signed callback handler in-process. A verified callback returns HTTP 200 with `{"received": true}`. Late successful payments and additional charges are recorded for reconciliation.

## Customer order history

Use a customer bearer token with `GET /api/v1/orders/` and `GET /api/v1/orders/{id}/`. The list supports `page`, `page_size`, `status`, and `ordering` (`-created_at` by default, or `created_at` for oldest first). The detail includes the order's saved address and amounts, item quantities and unit prices, and shop fulfillments. Item titles use the current catalog translation selected by `Accept-Language`.

Both endpoints summarize payment as `PENDING`, `FAILED`, `EXPIRED`, or `SUCCESS`. A successful charge takes precedence over other attempts. Use the order's `status` to determine whether the order was confirmed, including when a payment arrived after expiry.
