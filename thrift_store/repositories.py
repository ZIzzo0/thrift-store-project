from __future__ import annotations

import sqlite3


class UserRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_user(self, full_name: str, email: str, password_hash: str) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email.lower().strip(), password_hash),
        )
        return cursor.lastrowid

    def find_by_email(self, email: str):
        return self.connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()

    def find_by_id(self, user_id: int):
        return self.connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


class ProductRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_products(self):
        return self.connection.execute(
            "SELECT * FROM products WHERE stock > 0 ORDER BY id ASC"
        ).fetchall()

    def find_by_id(self, product_id: int):
        return self.connection.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

    def decrement_stock(self, product_id: int, quantity: int) -> None:
        self.connection.execute(
            """
            UPDATE products
            SET stock = stock - ?
            WHERE id = ? AND stock >= ?
            """,
            (quantity, product_id, quantity),
        )


class CartRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_items(self, owner_key: str):
        return self.connection.execute(
            """
            SELECT
                cart_items.id,
                cart_items.product_id,
                cart_items.quantity,
                products.title,
                products.brand,
                products.price_cents,
                products.image_url,
                products.stock
            FROM cart_items
            JOIN products ON products.id = cart_items.product_id
            WHERE owner_key = ?
            ORDER BY cart_items.id ASC
            """,
            (owner_key,),
        ).fetchall()

    def add_item(self, owner_key: str, product_id: int) -> None:
        self.connection.execute(
            """
            INSERT INTO cart_items (owner_key, product_id, quantity)
            VALUES (?, ?, 1)
            ON CONFLICT(owner_key, product_id)
            DO UPDATE SET quantity = quantity + 1
            """,
            (owner_key, product_id),
        )

    def remove_item(self, owner_key: str, product_id: int) -> None:
        self.connection.execute(
            "DELETE FROM cart_items WHERE owner_key = ? AND product_id = ?",
            (owner_key, product_id),
        )

    def clear(self, owner_key: str) -> None:
        self.connection.execute(
            "DELETE FROM cart_items WHERE owner_key = ?",
            (owner_key,),
        )


class OrderRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_order(
        self,
        *,
        user_id: int | None,
        guest_name: str | None,
        guest_email: str | None,
        shipping_address: str,
        city: str,
        country: str,
        payment_method: str,
        subtotal_cents: int,
        shipping_cents: int,
        total_cents: int,
        status: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO orders (
                user_id, guest_name, guest_email, shipping_address, city, country,
                payment_method, subtotal_cents, shipping_cents, total_cents, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                guest_name,
                guest_email,
                shipping_address,
                city,
                country,
                payment_method,
                subtotal_cents,
                shipping_cents,
                total_cents,
                status,
            ),
        )
        return cursor.lastrowid

    def add_order_item(
        self,
        *,
        order_id: int,
        product_id: int,
        title: str,
        unit_price_cents: int,
        quantity: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO order_items (order_id, product_id, title, unit_price_cents, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, product_id, title, unit_price_cents, quantity),
        )

    def get_order(self, order_id: int):
        return self.connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()

    def get_order_items(self, order_id: int):
        return self.connection.execute(
            """
            SELECT *
            FROM order_items
            WHERE order_id = ?
            ORDER BY id ASC
            """,
            (order_id,),
        ).fetchall()
