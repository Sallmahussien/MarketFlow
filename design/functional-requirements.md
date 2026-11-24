# Implemented functional requirements

MarketFlow lets customers buy from multiple shops in one checkout. It supports three account roles: customer, seller, and marketplace administrator.

## Accounts and seller onboarding

- Customers and sellers can register, sign in by email, edit their profile, and refresh or revoke their session tokens.
- A seller can apply for one shop. An administrator can approve or reject the application. A seller can resubmit a rejected application by making a meaningful edit.
- The public shop directory shows approved, active shops.

## Catalog and discovery

- Administrators can create, edit, deactivate, and reactivate categories.
- Approved sellers can manage drafts, prices, stock, and product image paths for their shop. Publishing requires at least one image. Sellers can choose a primary image, and removing the last image unpublishes the product.
- Public product search, sorting, and filters cover published, in-stock products in active categories and approved, active shops.
- Shop, category, and product text supports English and Arabic. Reads honor `Accept-Language` and fall back to English.

## Customer checkout and orders

- Customers can manage their own delivery addresses and add products from multiple shops to one active cart. The cart estimates totals using current prices and one shipping fee per shop with available items.
- Checkout validates every cart line, reserves stock, and saves the delivery address, item prices, and shipping fees. Cart edits are blocked during the 30-minute reservation.
- Checkout retries keep the original reservation deadline. Customers reuse an eligible link or get a new payment attempt. Expired orders release stock and make the cart editable.
- Customers can list and filter their orders and view saved amounts, delivery addresses, payment status, and each shop’s fulfillment.

## Payments and fulfillment

- The mock gateway simulates successful and failed payments. Signed callbacks validate the payment reference, amount, and currency. Repeated callbacks are safe to process.
- A successful payment confirms the order, deactivates the cart, and creates one fulfillment per shop.
- Sellers can list their shop’s fulfillments, edit tracking before delivery, and advance shipments from **Pending** to **Preparing**, **Shipped**, and **Delivered**. The order completes when every shipment is delivered.
- Administrators can filter payment attempts and identify late or additional successful charges that require reconciliation.

See the [OpenAPI contract](openapi.json) for routes, payloads, filters, and authentication.
