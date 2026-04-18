from __future__ import annotations

import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("THRIFT_STORE_DB_PATH", DATA_DIR / "thrift_store.db"))


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'customer',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    size TEXT NOT NULL,
    condition_label TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    image_url TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_key TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    UNIQUE(owner_key, product_id),
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    guest_name TEXT,
    guest_email TEXT,
    shipping_address TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    shipping_cents INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
"""


SEED_PRODUCTS = [
    {
        "title": "Vintage Denim Jacket",
        "brand": "Levi's",
        "category": "Outerwear",
        "size": "M",
        "condition_label": "Excellent",
        "price_cents": 4200,
        "description": "Classic blue denim jacket with a structured fit and light fade.",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=900&q=80",
        "stock": 1,
    },
    {
        "title": "Floral Midi Dress",
        "brand": "Zara",
        "category": "Dresses",
        "size": "S",
        "condition_label": "Very Good",
        "price_cents": 3100,
        "description": "Soft floral print dress with a light fabric and spring-ready silhouette.",
        "image_url": "https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=900&q=80",
        "stock": 1,
    },
    {
        "title": "Corduroy Overshirt",
        "brand": "Uniqlo",
        "category": "Shirts",
        "size": "L",
        "condition_label": "Excellent",
        "price_cents": 2800,
        "description": "Warm camel overshirt with roomy pockets and an easy layering fit.",
        "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80",
        "stock": 2,
    },
    {
        "title": "Retro Running Sneakers",
        "brand": "New Balance",
        "category": "Shoes",
        "size": "42",
        "condition_label": "Good",
        "price_cents": 3900,
        "description": "Comfortable retro sneakers with suede details and a cushioned sole.",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80",
        "stock": 1,
    },
    {
        "title": "Leather Crossbody Bag",
        "brand": "Mango",
        "category": "Accessories",
        "size": "One Size",
        "condition_label": "Very Good",
        "price_cents": 2600,
        "description": "Compact brown crossbody with adjustable strap and magnetic flap closure.",
        "image_url": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=900&q=80",
        "stock": 1,
    },
    {
        "title": "Chunky Knit Sweater",
        "brand": "H&M",
        "category": "Knitwear",
        "size": "M",
        "condition_label": "Excellent",
        "price_cents": 2400,
        "description": "Cozy cream sweater with a textured knit and relaxed shoulders.",
        "image_url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?auto=format&fit=crop&w=900&q=80",
        "stock": 3,
    },
]


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        existing = connection.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
        if existing:
            return
        connection.executemany(
            """
            INSERT INTO products (
                title, brand, category, size, condition_label, price_cents, description, image_url, stock
            ) VALUES (
                :title, :brand, :category, :size, :condition_label, :price_cents, :description, :image_url, :stock
            )
            """,
            SEED_PRODUCTS,
        )
