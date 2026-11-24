# MarketFlow database ERD

This diagram shows the PostgreSQL tables defined by the marketplace apps. `PK` marks a primary key, `FK` a foreign key, `UQ` a unique column, and `NULL` an optional field. Cardinalities read from top to bottom. The [foreign key index](#foreign-key-index) lists all table-to-table references.

## Accounts and shops

```text
                     ┌─────────────────────────────────────┐
                     │            accounts_user            │
                     ├─────────────────────────────────────┤
                     │ id bigint PK                        │
                     │ password varchar(128)               │
                     │ last_login timestamptz NULL         │
                     │ is_superuser boolean                │
                     │ username varchar(150) UQ            │
                     │ first_name varchar(150)             │
                     │ last_name varchar(150)              │
                     │ is_staff boolean                    │
                     │ is_active boolean                   │
                     │ date_joined timestamptz             │
                     │ email varchar(254) UQ               │
                     │ phone varchar(20)                   │
                     │ profile_image varchar(255) NULL     │
                     │ role varchar(10)                    │
                     │ created_at timestamptz              │
                     │ updated_at timestamptz              │
                     └─────────────────────────────────────┘
                                        │  1
                   ┌────────────────────┴────────────────────┐
                   │  0..N                                   │  0..1
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│           accounts_address          │   │              shops_shop             │
├─────────────────────────────────────┤   ├─────────────────────────────────────┤
│ id bigint PK                        │   │ id bigint PK                        │
│ user_id bigint FK                   │   │ user_id bigint FK UQ                │
│ first_name varchar(150)             │   │ name jsonb                          │
│ last_name varchar(150)              │   │ description jsonb                   │
│ phone_number varchar(20)            │   │ logo_url varchar(500) NULL          │
│ building varchar(100)               │   │ shipping_fee numeric(10, 2)         │
│ street_name varchar(255)            │   │ status varchar(10)                  │
│ apartment varchar(100)              │   │ is_active boolean                   │
│ city varchar(100)                   │   │ rejection_reason text NULL          │
│ governorate varchar(100)            │   │ created_at timestamptz              │
│ postal_code varchar(20)             │   │ updated_at timestamptz              │
│ created_at timestamptz              │   └─────────────────────────────────────┘
│ updated_at timestamptz              │
└─────────────────────────────────────┘
```

## Catalog and cart

Products belong to a shop and category. A cart item links its cart to a product.

```text
                     ┌─────────────────────────────────────┐
                     │           catalog_product           │
                     ├─────────────────────────────────────┤
                     │ id bigint PK                        │
                     │ shop_id bigint FK                   │
                     │ category_id bigint FK               │
                     │ title jsonb                         │
                     │ description jsonb                   │
                     │ price numeric(10, 2)                │
                     │ stock integer                       │
                     │ is_published boolean                │
                     │ created_at timestamptz              │
                     │ updated_at timestamptz              │
                     └─────────────────────────────────────┘
                                        │  1
                   ┌────────────────────┴────────────────────┐
                   │  0..N                                   │  0..N
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│         catalog_productimage        │   │            carts_cartitem           │
├─────────────────────────────────────┤   ├─────────────────────────────────────┤
│ id bigint PK                        │   │ id bigint PK                        │
│ product_id bigint FK                │   │ cart_id bigint FK                   │
│ image_path varchar(500)             │   │ product_id bigint FK                │
│ is_primary boolean                  │   │ quantity integer                    │
│ created_at timestamptz              │   │ created_at timestamptz              │
│ updated_at timestamptz              │   │ updated_at timestamptz              │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
```

```text
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│           catalog_category          │   │              carts_cart             │
├─────────────────────────────────────┤   ├─────────────────────────────────────┤
│ id bigint PK                        │   │ id bigint PK                        │
│ name jsonb                          │   │ user_id bigint FK                   │
│ description jsonb                   │   │ is_active boolean                   │
│ icon_url varchar(500) NULL          │   │ created_at timestamptz              │
│ is_active boolean                   │   │ updated_at timestamptz              │
│ created_at timestamptz              │   └─────────────────────────────────────┘
│ updated_at timestamptz              │
└─────────────────────────────────────┘
```

## Orders and fulfillment

Checkout stores delivery and shipping details on the order. A fulfillment groups the order items assigned to one shop.

```text
                     ┌─────────────────────────────────────┐
                     │             orders_order            │
                     ├─────────────────────────────────────┤
                     │ id bigint PK                        │
                     │ user_id bigint FK                   │
                     │ cart_id bigint FK                   │
                     │ status varchar(24)                  │
                     │ address_snapshot jsonb              │
                     │ shipping_by_shop jsonb              │
                     │ subtotal numeric(12, 2)             │
                     │ shipping_total numeric(12, 2)       │
                     │ total_amount numeric(12, 2)         │
                     │ currency varchar(3)                 │
                     │ created_at timestamptz              │
                     │ expires_at timestamptz              │
                     │ updated_at timestamptz              │
                     └─────────────────────────────────────┘
                                        │  1
                   ┌────────────────────┴────────────────────┐
                   │  0..N                                   │  0..N
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│           orders_orderitem          │   │       fulfillments_fulfillment      │
├─────────────────────────────────────┤   ├─────────────────────────────────────┤
│ id bigint PK                        │   │ id bigint PK                        │
│ order_id bigint FK                  │   │ order_id bigint FK                  │
│ product_id bigint FK                │   │ shop_id bigint FK                   │
│ shop_id bigint FK                   │   │ shipping_fee numeric(10, 2)         │
│ unit_price numeric(10, 2)           │   │ status varchar(16)                  │
│ quantity integer                    │   │ tracking_number varchar(150) NULL   │
│ status varchar(10)                  │   │ carrier_name varchar(150) NULL      │
│ fulfillment_id bigint FK NULL       │   │ created_at timestamptz              │
└─────────────────────────────────────┘   │ updated_at timestamptz              │
                                          └─────────────────────────────────────┘
```

## Payments

Each attempt belongs to an order. Verified gateway notifications are recorded as payment events.

```text
                     ┌─────────────────────────────────────┐
                     │           payments_payment          │
                     ├─────────────────────────────────────┤
                     │ id bigint PK                        │
                     │ order_id bigint FK                  │
                     │ provider varchar(32)                │
                     │ reference uuid UQ                   │
                     │ session_id varchar(255)             │
                     │ transaction_id varchar(255) NULL    │
                     │ payment_url varchar(2000)           │
                     │ expires_at timestamptz              │
                     │ state varchar(16)                   │
                     │ created_at timestamptz              │
                     │ updated_at timestamptz              │
                     └─────────────────────────────────────┘
                                        │  1 → 0..N
                                        │
                     ┌─────────────────────────────────────┐
                     │        payments_paymentevent        │
                     ├─────────────────────────────────────┤
                     │ id bigint PK                        │
                     │ payment_id bigint FK                │
                     │ event_id varchar(255)               │
                     │ transaction_id varchar(255)         │
                     │ outcome varchar(10)                 │
                     │ amount numeric(12, 2)               │
                     │ currency varchar(3)                 │
                     │ attention_reason varchar(80)        │
                     │ received_at timestamptz             │
                     └─────────────────────────────────────┘
```

The local mock gateway stores sessions separately. It looks up `payments_payment.reference` and `orders_order.id` using its reference values.

```text
┌─────────────────────────────────────┐
│         payments_mocksession        │
├─────────────────────────────────────┤
│ id bigint PK                        │
│ reference uuid UQ                   │
│ token uuid UQ                       │
│ transaction_id uuid UQ              │
│ order_reference bigint              │
│ amount numeric(12, 2)               │
│ currency varchar(3)                 │
│ expires_at timestamptz              │
│ outcome varchar(10)                 │
└─────────────────────────────────────┘
```

## Foreign key index

The parent can have zero or more child rows by default. The seller relationship is one-to-zero-or-one. Every child has one parent for each foreign key, with the exception of the optional fulfillment on an order item.

| Child table | Foreign key references |
| --- | --- |
| `accounts_address` | `user_id → accounts_user.id` |
| `shops_shop` | `user_id → accounts_user.id` (unique) |
| `catalog_product` | `shop_id → shops_shop.id`, `category_id → catalog_category.id` |
| `catalog_productimage` | `product_id → catalog_product.id` |
| `carts_cart` | `user_id → accounts_user.id` |
| `carts_cartitem` | `cart_id → carts_cart.id`, `product_id → catalog_product.id` |
| `orders_order` | `user_id → accounts_user.id`, `cart_id → carts_cart.id` |
| `orders_orderitem` | `order_id → orders_order.id`, `product_id → catalog_product.id`, `shop_id → shops_shop.id`, `fulfillment_id → fulfillments_fulfillment.id` (nullable) |
| `fulfillments_fulfillment` | `order_id → orders_order.id`, `shop_id → shops_shop.id` |
| `payments_payment` | `order_id → orders_order.id` |
| `payments_paymentevent` | `payment_id → payments_payment.id` |

## Database constraints

| Rule | Enforced by |
| --- | --- |
| A customer has at most one active cart. | Partial unique constraint on cart `user_id` where `is_active` is true |
| A cart has at most one line per product. | Unique `(cart_id, product_id)` |
| Each product has at most one primary image. | Partial unique constraint on image `product_id` where `is_primary` is true |
| A cart has at most one pending payment order. | Partial unique constraint on order `cart_id` where `status = PENDING_PAYMENT` |
| An order has at most one open payment attempt. | Partial unique constraint on payment `order_id` for `CREATING`, `OPEN`, and `PROCESSING` |
| A gateway transaction identifies a charge. | Unique payment `(provider, transaction_id)` when the transaction ID is present |
| A notification is processed once per attempt. | Unique payment event `(payment_id, event_id)` |
| Each shop has one fulfillment per paid order. | Unique fulfillment `(order_id, shop_id)` |

Django’s authentication, token blacklist, and framework-generated tables are outside this diagram. The model definitions and migration files in [apps/](../apps/) are the source for the complete schema.
