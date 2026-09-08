# Data Model Design: Online Marketplace Orders

**Story:** story-adhoc-1788892533
**Difficulty:** Intermediate  
**Scenario:** An online marketplace lets customers place orders containing multiple products. Inventory is tracked, and each order records the price and quantity agreed at checkout.

## Overview

Four tables represent customers, products, orders, and order items. `order_items` is an attributed join table: a customer can buy many products, and a product can appear in many orders, while preserving the historical unit price for each purchase.

## Entity-relationship summary

```text
customers 1 ----< orders 1 ----< order_items >---- 1 products
```

- One customer can have many orders.
- One order contains one or more order items.
- One product can appear in many order items.
- `orders` and `products` have a many-to-many relationship through `order_items`.

## Tables

### 1. `customers`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BIGINT | PRIMARY KEY | Surrogate key |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Account/contact identity |
| `full_name` | VARCHAR(200) | NOT NULL | Customer display name |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Audit timestamp |
| `status` | VARCHAR(20) | NOT NULL, CHECK in (`active`, `suspended`) | Prevents new orders for suspended accounts |

### 2. `products`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BIGINT | PRIMARY KEY | Product identifier |
| `sku` | VARCHAR(64) | NOT NULL, UNIQUE | Stable inventory/business key |
| `name` | VARCHAR(200) | NOT NULL | Catalog name |
| `current_price` | NUMERIC(12,2) | NOT NULL, CHECK > 0 | Current catalog price; not used to rewrite old orders |
| `stock_quantity` | INTEGER | NOT NULL, CHECK >= 0 | Available units |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Soft-retire a product |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Audit timestamp |

Indexes: unique indexes on `sku`; an index on `(is_active, name)` supports catalog browsing.

### 3. `orders`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BIGINT | PRIMARY KEY | Order identifier |
| `customer_id` | BIGINT | NOT NULL, FK -> `customers(id)` | Buyer |
| `status` | VARCHAR(20) | NOT NULL, CHECK in (`pending`, `paid`, `shipped`, `cancelled`, `refunded`) | Order lifecycle |
| `total_amount` | NUMERIC(12,2) | NOT NULL, CHECK >= 0 | Materialized total for receipt/reporting |
| `placed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation time |
| `shipping_address` | JSONB | NOT NULL | Snapshot so later profile edits do not change delivery data |

Indexes: `(customer_id, placed_at DESC)` for order history and `(status, placed_at)` for fulfillment queues.

### 4. `order_items` (relationship table)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | BIGINT | PRIMARY KEY | Line-item identifier |
| `order_id` | BIGINT | NOT NULL, FK -> `orders(id)` ON DELETE CASCADE | Owning order |
| `product_id` | BIGINT | NOT NULL, FK -> `products(id)` | Purchased product |
| `quantity` | INTEGER | NOT NULL, CHECK > 0 | Units purchased |
| `unit_price` | NUMERIC(12,2) | NOT NULL, CHECK >= 0 | Price captured at checkout |
| `line_total` | NUMERIC(12,2) | NOT NULL, CHECK >= 0 | `quantity * unit_price`, calculated by the application or generated column |

Constraints and indexes:

- `UNIQUE (order_id, product_id)` prevents duplicate lines for one product in an order.
- Index `(product_id)` supports sales history and product reporting.
- Index `(order_id)` supports receipt and fulfillment queries.

## Relationship rules

| From | To | Cardinality | Rule |
|---|---|---|---|
| `orders.customer_id` | `customers.id` | N : 1 | A customer may have many orders; retain orders if a customer is deactivated. |
| `order_items.order_id` | `orders.id` | N : 1 | Deleting a draft order cascades to its lines. Production systems may prohibit deleting paid orders. |
| `order_items.product_id` | `products.id` | N : 1 | Product deletion should normally be restricted once referenced by an order. |
| `orders` | `products` | M : N | Implemented through `order_items`, which carries quantity and historical price. |

## Integrity and transaction rules

1. Only an `active` customer may create a new order.
2. Checkout runs in one transaction: lock each product row, verify stock, decrement `stock_quantity`, insert `order_items`, calculate `total_amount`, and transition the order to `paid`.
3. `orders.total_amount` must equal the sum of `order_items.line_total`; enforce this in application/service logic because a normal row-level `CHECK` cannot aggregate child rows.
4. A paid or shipped order is never hard-deleted. Cancellation/refund transitions are recorded through `status` and an audit/event mechanism if full history is required.
5. Product price changes affect only `products.current_price`; `order_items.unit_price` remains immutable after payment.

## Example PostgreSQL DDL sketch

```sql
CREATE TABLE customers (
  id         BIGSERIAL PRIMARY KEY,
  email      VARCHAR(255) NOT NULL UNIQUE,
  full_name  VARCHAR(200) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status     VARCHAR(20) NOT NULL CHECK (status IN ('active', 'suspended'))
);

CREATE TABLE products (
  id             BIGSERIAL PRIMARY KEY,
  sku            VARCHAR(64) NOT NULL UNIQUE,
  name           VARCHAR(200) NOT NULL,
  current_price  NUMERIC(12,2) NOT NULL CHECK (current_price > 0),
  stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
  id               BIGSERIAL PRIMARY KEY,
  customer_id      BIGINT NOT NULL REFERENCES customers(id),
  status           VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'paid', 'shipped', 'cancelled', 'refunded')),
  total_amount     NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
  placed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  shipping_address JSONB NOT NULL
);

CREATE TABLE order_items (
  id         BIGSERIAL PRIMARY KEY,
  order_id   BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id BIGINT NOT NULL REFERENCES products(id),
  quantity   INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
  line_total NUMERIC(12,2) NOT NULL CHECK (line_total >= 0),
  UNIQUE (order_id, product_id)
);

CREATE INDEX idx_orders_customer_placed ON orders (customer_id, placed_at DESC);
CREATE INDEX idx_order_items_product ON order_items (product_id);
```

## Why this is intermediate

The model goes beyond a simple parent-child pair by using an attributed many-to-many relationship, historical snapshots, lifecycle constraints, and a cross-table inventory/total transaction. It also distinguishes database-enforceable row rules from business invariants that require a transaction or service layer.
