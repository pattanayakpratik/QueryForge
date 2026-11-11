"""Seeds a realistic 5-table SaaS & E-Commerce database for Text-to-SQL benchmarking.

Tables:
- customers
- products
- orders
- order_items
- refunds
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Add project root to sys.path so script can run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Numeric,
    select,
    text,
)
from sqlalchemy.orm import declarative_base
from app.config import get_settings
from app.database import get_target_engine

DemoBase = declarative_base()


class Customer(DemoBase):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), unique=True, nullable=False)
    country = Column(String(3), nullable=False)  # ISO code: US, UK, CA, DE, IN
    signup_date = Column(DateTime, nullable=False)


class Product(DemoBase):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    price_cents = Column(Integer, nullable=False)
    stock_count = Column(Integer, nullable=False)


class Order(DemoBase):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    status = Column(String(32), nullable=False)  # 'completed', 'refunded', 'pending'
    total_amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


class OrderItem(DemoBase):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_cents = Column(Integer, nullable=False)


class Refund(DemoBase):
    __tablename__ = "refunds"
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    reason = Column(String(128), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False)


# Seed Data Generators
COUNTRIES = ["US", "UK", "CA", "DE", "IN", "FR", "JP", "AU"]
CATEGORIES = ["Analytics", "Cloud Hosting", "Developer Tools", "AI Credits", "Security"]

PRODUCT_SEEDS = [
    ("Pro Analytics Seat", "Analytics", 4900, 1000),
    ("Enterprise BI Cluster", "Analytics", 29900, 500),
    ("Managed Vector DB Instance", "Cloud Hosting", 12900, 300),
    ("GPU Inference Runner (100h)", "AI Credits", 8500, 2000),
    ("SQL AST Firewall Appliance", "Security", 15000, 150),
    ("Automated Audit Log Vault", "Security", 9900, 450),
    ("Query Cache Node", "Cloud Hosting", 4500, 800),
    ("API Gateway Ingress Tier", "Developer Tools", 6500, 600),
    ("Database Migration Toolkit", "Developer Tools", 3900, 950),
    ("AI Prompt Studio License", "AI Credits", 7500, 1200),
]

REFUND_REASONS = [
    "Duplicate purchase",
    "Customer requested cancellation",
    "Trial expired without renewal",
    "Billing currency mismatch",
    "Feature incompatible with database",
]


async def seed_ecommerce_database(target_url: str | None = None) -> None:
    """Populate target database with realistic tables and sample records."""
    settings = get_settings()
    db_url = target_url or settings.target_database_url
    engine = get_target_engine(db_url)

    print(f"[*] Initializing tables on target database: {db_url}")
    async with engine.begin() as conn:
        await conn.run_sync(DemoBase.metadata.drop_all)
        await conn.run_sync(DemoBase.metadata.create_all)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    random.seed(42)

    async with engine.begin() as conn:
        # 1. Insert Customers
        print("[*] Seeding 50 customers...")
        customers_to_insert = []
        for i in range(1, 51):
            signup = now - timedelta(days=random.randint(30, 240))
            customers_to_insert.append(
                {
                    "name": f"User {i:03d}",
                    "email": f"user{i:03d}@enterprise-{random.choice(['corp', 'io', 'tech', 'dev'])}.com",
                    "country": random.choice(COUNTRIES),
                    "signup_date": signup,
                }
            )
        await conn.execute(Customer.__table__.insert(), customers_to_insert)

        # 2. Insert Products
        print("[*] Seeding products catalog...")
        products_to_insert = [
            {
                "name": name,
                "category": category,
                "price_cents": price,
                "stock_count": stock,
            }
            for name, category, price, stock in PRODUCT_SEEDS
        ]
        await conn.execute(Product.__table__.insert(), products_to_insert)

        # 3. Insert Orders & Order Items across last 6 months
        print("[*] Seeding 200 orders and order items...")
        orders_to_insert = []
        order_items_to_insert = []
        refunds_to_insert = []

        for order_id in range(1, 201):
            customer_id = random.randint(1, 50)
            order_date = now - timedelta(days=random.randint(1, 180), hours=random.randint(0, 23))
            is_refunded = random.random() < 0.15  # ~15% refund rate
            status = "refunded" if is_refunded else "completed"

            # 1-3 items per order
            num_items = random.randint(1, 3)
            order_total = 0
            for _ in range(num_items):
                prod_idx = random.randint(0, len(PRODUCT_SEEDS) - 1)
                unit_price = PRODUCT_SEEDS[prod_idx][2]
                qty = random.randint(1, 2)
                item_total = unit_price * qty
                order_total += item_total

                order_items_to_insert.append(
                    {
                        "order_id": order_id,
                        "product_id": prod_idx + 1,
                        "quantity": qty,
                        "unit_price_cents": unit_price,
                    }
                )

            orders_to_insert.append(
                {
                    "id": order_id,
                    "customer_id": customer_id,
                    "status": status,
                    "total_amount_cents": order_total,
                    "created_at": order_date,
                }
            )

            if is_refunded:
                refund_date = order_date + timedelta(days=random.randint(1, 7))
                refunds_to_insert.append(
                    {
                        "order_id": order_id,
                        "reason": random.choice(REFUND_REASONS),
                        "amount_cents": order_total,
                        "created_at": refund_date,
                    }
                )

        await conn.execute(Order.__table__.insert(), orders_to_insert)
        await conn.execute(OrderItem.__table__.insert(), order_items_to_insert)

        # 4. Insert Refunds
        if refunds_to_insert:
            print(f"[*] Seeding {len(refunds_to_insert)} refunds...")
            await conn.execute(Refund.__table__.insert(), refunds_to_insert)

    print(
        f"[+] Seed complete! Inserted: 50 customers, {len(PRODUCT_SEEDS)} products, "
        f"{len(orders_to_insert)} orders, {len(order_items_to_insert)} items, {len(refunds_to_insert)} refunds."
    )


if __name__ == "__main__":
    asyncio.run(seed_ecommerce_database())
