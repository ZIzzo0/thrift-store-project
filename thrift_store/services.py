from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from thrift_store.repositories import CartRepository, OrderRepository, ProductRepository, UserRepository


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def format_money(cents: int) -> str:
    return f"${cents / 100:.2f}"


@dataclass
class CartSummary:
    items: list
    subtotal_cents: int
    shipping_cents: int
    total_cents: int
    item_count: int


class AuthService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.users = UserRepository(connection)

    def register(self, full_name: str, email: str, password: str) -> int:
        if not full_name.strip():
            raise ValueError("Full name is required.")
        if "@" not in email or "." not in email:
            raise ValueError("Enter a valid email address.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        if self.users.find_by_email(email):
            raise ValueError("An account with that email already exists.")
        return self.users.create_user(full_name.strip(), email.strip(), hash_password(password))

    def login(self, email: str, password: str):
        user = self.users.find_by_email(email)
        if not user or user["password_hash"] != hash_password(password):
            raise ValueError("Incorrect email or password.")
        return user


class CatalogService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.products = ProductRepository(connection)

    def list_products(self):
        return self.products.list_products()

    def get_product(self, product_id: int):
        product = self.products.find_by_id(product_id)
        if not product:
            raise ValueError("Product not found.")
        return product


class CartService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.cart = CartRepository(connection)
        self.products = ProductRepository(connection)

    def add_item(self, owner_key: str, product_id: int) -> None:
        product = self.products.find_by_id(product_id)
        if not product or product["stock"] <= 0:
            raise ValueError("That product is unavailable.")
        self.cart.add_item(owner_key, product_id)
        self.connection.commit()

    def remove_item(self, owner_key: str, product_id: int) -> None:
        self.cart.remove_item(owner_key, product_id)
        self.connection.commit()

    def get_summary(self, owner_key: str) -> CartSummary:
        items = self.cart.list_items(owner_key)
        subtotal_cents = sum(item["price_cents"] * item["quantity"] for item in items)
        shipping_cents = 699 if subtotal_cents and subtotal_cents < 8000 else 0
        total_cents = subtotal_cents + shipping_cents
        item_count = sum(item["quantity"] for item in items)
        return CartSummary(
            items=list(items),
            subtotal_cents=subtotal_cents,
            shipping_cents=shipping_cents,
            total_cents=total_cents,
            item_count=item_count,
        )


class CheckoutService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.cart_service = CartService(connection)
        self.products = ProductRepository(connection)
        self.cart = CartRepository(connection)
        self.orders = OrderRepository(connection)

    def checkout(
        self,
        *,
        owner_key: str,
        user_id: int | None,
        guest_name: str | None,
        guest_email: str | None,
        shipping_address: str,
        city: str,
        country: str,
        payment_method: str,
    ) -> int:
        summary = self.cart_service.get_summary(owner_key)
        if not summary.items:
            raise ValueError("Your cart is empty.")
        if user_id is None:
            if not guest_name or not guest_name.strip():
                raise ValueError("Guest name is required for guest checkout.")
            if not guest_email or "@" not in guest_email:
                raise ValueError("A valid guest email is required.")
        if not shipping_address.strip() or not city.strip() or not country.strip():
            raise ValueError("Shipping address, city, and country are required.")
        if payment_method not in {"card", "cod"}:
            raise ValueError("Choose a supported payment method.")

        for item in summary.items:
            product = self.products.find_by_id(item["product_id"])
            if not product or product["stock"] < item["quantity"]:
                raise ValueError(f"{item['title']} is no longer in stock.")

        order_id = self.orders.create_order(
            user_id=user_id,
            guest_name=guest_name.strip() if guest_name else None,
            guest_email=guest_email.strip() if guest_email else None,
            shipping_address=shipping_address.strip(),
            city=city.strip(),
            country=country.strip(),
            payment_method=payment_method,
            subtotal_cents=summary.subtotal_cents,
            shipping_cents=summary.shipping_cents,
            total_cents=summary.total_cents,
            status="confirmed",
        )

        for item in summary.items:
            self.orders.add_order_item(
                order_id=order_id,
                product_id=item["product_id"],
                title=item["title"],
                unit_price_cents=item["price_cents"],
                quantity=item["quantity"],
            )
            self.products.decrement_stock(item["product_id"], item["quantity"])

        self.cart.clear(owner_key)
        self.connection.commit()
        return order_id
