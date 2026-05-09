from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from thrift_store.app import create_app
from thrift_store import database
from thrift_store.services import AuthService, CartService, CatalogService, CheckoutService, ReviewService, SellerService
from thrift_store.views import render_home, render_product, render_seller_dashboard


class ThriftStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        fd, temp_path = tempfile.mkstemp(prefix="rethread_test_", suffix=".db", dir=Path(__file__).resolve().parent / "data")
        os.close(fd)
        self.db_path = Path(temp_path)
        database.DB_PATH = self.db_path
        database.initialize_database()

    def test_registration_and_login(self) -> None:
        from thrift_store.database import get_connection

        with get_connection() as connection:
            auth = AuthService(connection)
            user_id = auth.register("Test User", "test@example.com", "secret1", "secret1")
            connection.commit()
            user = auth.login("test@example.com", "secret1")
        self.assertEqual(user_id, user["id"])

    def test_registration_requires_matching_password_confirmation(self) -> None:
        from thrift_store.database import get_connection

        with get_connection() as connection:
            auth = AuthService(connection)
            with self.assertRaisesRegex(ValueError, "Passwords do not match"):
                auth.register("Test User", "test@example.com", "secret1", "secret2")

    def test_registration_can_create_seller_account(self) -> None:
        from thrift_store.database import get_connection

        with get_connection() as connection:
            auth = AuthService(connection)
            user_id = auth.register("Seller User", "seller-signup@example.com", "secret1", "secret1", "seller")
            connection.commit()
            user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        self.assertEqual(user["role"], "seller")

    def test_register_page_shows_customer_and_seller_choices(self) -> None:
        app = create_app()
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = dict(headers)

        response = app(
            {
                "PATH_INFO": "/register",
                "REQUEST_METHOD": "GET",
                "CONTENT_LENGTH": "0",
                "wsgi.input": BytesIO(b""),
            },
            start_response,
        )

        page = b"".join(response).decode("utf-8")
        self.assertEqual(status_headers["status"], "200 OK")
        self.assertIn("Register as", page)
        self.assertIn('value="customer"', page)
        self.assertIn('value="seller"', page)

    def test_registration_route_redirects_seller_to_dashboard(self) -> None:
        app = create_app()
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = dict(headers)

        body = (
            b"account_type=seller&full_name=Seller+Route&email=seller-route%40example.com"
            b"&password=secret1&confirm_password=secret1"
        )
        response = app(
            {
                "PATH_INFO": "/register",
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": str(len(body)),
                "wsgi.input": BytesIO(body),
            },
            start_response,
        )

        with database.get_connection() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", ("seller-route@example.com",)).fetchone()

        self.assertEqual(status_headers["status"], "302 Found")
        self.assertEqual(status_headers["headers"]["Location"], "/seller")
        self.assertEqual(response, [b""])
        self.assertEqual(user["role"], "seller")

    def test_seller_dashboard_uses_seller_ui(self) -> None:
        page = render_seller_dashboard(
            [
                {
                    "id": 1,
                    "title": "Seller Jacket",
                    "category": "Outerwear",
                    "price_cents": 4200,
                    "stock": 3,
                }
            ],
            [
                {
                    "id": 1,
                    "status": "packed",
                    "total_cents": 4200,
                }
            ],
            current_user={"full_name": "Studio Seller", "role": "seller"},
            cart_count=0,
            order_statuses=["packed", "shipped"],
        ).decode("utf-8")

        self.assertIn('class="seller-mode"', page)
        self.assertIn("ReThread Studio", page)
        self.assertIn("Seller Studio", page)
        self.assertIn("seller-stats", page)
        self.assertIn("Add Listing", page)
        self.assertIn("Shopper Mode", page)
        self.assertNotIn("Cart (", page)
        self.assertNotIn("Storefront", page)

    def test_seller_can_use_shopper_mode_to_buy(self) -> None:
        with database.get_connection() as connection:
            product = connection.execute("SELECT * FROM products WHERE stock > 0 ORDER BY id ASC LIMIT 1").fetchone()

        page = render_product(
            product,
            cart_count=0,
            current_user={"full_name": "Studio Seller", "role": "seller"},
        ).decode("utf-8")

        self.assertIn('class="shopper-mode"', page)
        self.assertIn("Seller Studio", page)
        self.assertIn("Add item to cart", page)
        self.assertNotIn("Seller accounts manage listings and cannot buy items.", page)

    def test_seller_can_add_items_to_cart_in_shopper_mode(self) -> None:
        app = create_app()
        session_id = "seller-cart-session"
        with database.get_connection() as connection:
            seller_id = AuthService(connection).register("Seller Buyer", "seller-buyer@example.com", "secret1", "secret1", "seller")
            connection.commit()
        app.sessions[session_id] = {"session_id": session_id, "user_id": seller_id}
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = dict(headers)

        body = b"product_id=1"
        response = app(
            {
                "PATH_INFO": "/cart/add",
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": str(len(body)),
                "HTTP_COOKIE": f"session_id={session_id}",
                "wsgi.input": BytesIO(body),
            },
            start_response,
        )

        with database.get_connection() as connection:
            summary = CartService(connection).get_summary(f"user:{seller_id}")

        self.assertEqual(status_headers["status"], "302 Found")
        self.assertEqual(response, [b""])
        self.assertEqual(summary.item_count, 1)

    def test_guest_checkout_flow(self) -> None:
        from thrift_store.database import get_connection

        owner_key = "guest:test-session"
        with get_connection() as connection:
            cart = CartService(connection)
            cart.add_item(owner_key, 1)
            summary = cart.get_summary(owner_key)
            self.assertEqual(summary.item_count, 1)
            order_id = CheckoutService(connection).checkout(
                owner_key=owner_key,
                user_id=None,
                guest_name="Guest Buyer",
                guest_email="guest@example.com",
                shipping_address="12 Main Street",
                city="Cairo",
                country="Egypt",
                payment_method="cod",
            )
            self.assertGreater(order_id, 0)
            self.assertEqual(cart.get_summary(owner_key).item_count, 0)

    def test_app_boots(self) -> None:
        app = create_app()
        self.assertIsNotNone(app)

    def test_catalog_keeps_sold_out_items_visible(self) -> None:
        from thrift_store.database import get_connection
        from thrift_store.services import CatalogService

        with get_connection() as connection:
            connection.execute("UPDATE products SET stock = 0 WHERE id = 1")
            connection.commit()
            products = CatalogService(connection).list_products()

        self.assertTrue(any(product["id"] == 1 and product["stock"] == 0 for product in products))

    def test_home_page_shows_stock_count_and_sold_out_state(self) -> None:
        with database.get_connection() as connection:
            available = connection.execute("SELECT * FROM products WHERE stock > 0 ORDER BY id ASC LIMIT 1").fetchone()
            sold_out = connection.execute("SELECT * FROM products WHERE stock = 0 ORDER BY id ASC LIMIT 1").fetchone()

        page = render_home([available, sold_out], cart_count=0).decode("utf-8")
        sold_out_slice = page.split(sold_out["title"], maxsplit=1)[1]

        self.assertIn(f"{available['stock']} left in stock", page)
        self.assertIn("Sold out", page)
        self.assertNotIn("Add to cart", sold_out_slice)

    def test_product_page_disables_cart_cta_when_sold_out(self) -> None:
        with database.get_connection() as connection:
            sold_out = connection.execute("SELECT * FROM products WHERE stock = 0 ORDER BY id ASC LIMIT 1").fetchone()

        page = render_product(sold_out, cart_count=0).decode("utf-8")

        self.assertIn("Sold out right now. Check back soon.", page)
        self.assertNotIn("Add item to cart", page)

    def test_reset_database_restores_default_state(self) -> None:
        with database.get_connection() as connection:
            connection.execute("INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)", ("Reset Me", "reset@example.com", "hash"))
            connection.execute("UPDATE products SET stock = 0 WHERE id = 1")
            connection.commit()

        database.reset_database()

        with database.get_connection() as connection:
            user_count = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            restored_product = connection.execute("SELECT stock FROM products WHERE id = 1").fetchone()

        self.assertEqual(user_count, 0)
        self.assertEqual(restored_product["stock"], 1)

    def test_reset_route_redirects_home(self) -> None:
        app = create_app()
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = dict(headers)

        response = app(
            {
                "PATH_INFO": "/reset",
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": "0",
                "wsgi.input": BytesIO(b""),
            },
            start_response,
        )

        self.assertEqual(status_headers["status"], "302 Found")
        self.assertEqual(status_headers["headers"]["Location"], "/")
        self.assertEqual(response, [b""])

    def test_search_and_filter_products(self) -> None:
        with database.get_connection() as connection:
            catalog = CatalogService(connection)
            search_results = catalog.list_products(search="denim")
            filtered_results = catalog.list_products(category="Shoes", size="42")

        self.assertTrue(any(product["title"] == "Vintage Denim Jacket" for product in search_results))
        self.assertTrue(filtered_results)
        self.assertTrue(all(product["category"] == "Shoes" and product["size"] == "42" for product in filtered_results))

    def test_leave_product_review(self) -> None:
        with database.get_connection() as connection:
            reviews = ReviewService(connection)
            review_id = reviews.leave_review(
                product_id=1,
                user_id=None,
                reviewer_name="Guest Reviewer",
                rating="5",
                comment="Great quality and fast checkout.",
            )
            stored_reviews = reviews.list_reviews(1)

        self.assertGreater(review_id, 0)
        self.assertEqual(stored_reviews[0]["reviewer_name"], "Guest Reviewer")
        self.assertEqual(stored_reviews[0]["rating"], 5)

    def test_seller_can_register_and_manage_product_listing(self) -> None:
        with database.get_connection() as connection:
            auth = AuthService(connection)
            user_id = auth.register("Seller User", "seller@example.com", "secret1", "secret1")
            connection.commit()
            auth.register_seller(user_id)
            seller = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

            seller_service = SellerService(connection)
            product_id = seller_service.create_listing(
                user_id,
                {
                    "title": "Seller Silk Scarf",
                    "brand": "Local Vintage",
                    "category": "Accessories",
                    "size": "One Size",
                    "condition_label": "Excellent",
                    "price": "18.50",
                    "description": "Soft printed scarf selected by an independent seller.",
                    "image_url": "https://example.com/scarf.jpg",
                    "stock": "2",
                },
            )
            seller_service.update_listing(
                user_id,
                product_id,
                {
                    "title": "Seller Silk Scarf",
                    "brand": "Local Vintage",
                    "category": "Accessories",
                    "size": "One Size",
                    "condition_label": "Excellent",
                    "price": "20.00",
                    "description": "Soft printed scarf selected by an independent seller.",
                    "image_url": "https://example.com/scarf.jpg",
                    "stock": "3",
                },
            )
            updated = seller_service.get_listing(user_id, product_id)
            seller_service.delete_listing(user_id, product_id)
            deleted = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

        self.assertEqual(seller["role"], "seller")
        self.assertEqual(updated["price_cents"], 2000)
        self.assertIsNone(deleted)

    def test_seller_registration_confirmation_page_requires_logged_in_user(self) -> None:
        app = create_app()
        status_headers = {}

        def start_response(status, headers):
            status_headers["status"] = status
            status_headers["headers"] = dict(headers)

        response = app(
            {
                "PATH_INFO": "/seller/register",
                "REQUEST_METHOD": "GET",
                "CONTENT_LENGTH": "0",
                "wsgi.input": BytesIO(b""),
            },
            start_response,
        )

        self.assertEqual(status_headers["status"], "302 Found")
        self.assertEqual(status_headers["headers"]["Location"], "/")
        self.assertEqual(response, [b""])

    def test_seller_registration_confirmation_activates_seller(self) -> None:
        app = create_app()
        session_id = "seller-confirm-session"
        with database.get_connection() as connection:
            user_id = AuthService(connection).register("Seller User", "seller-confirm@example.com", "secret1", "secret1")
            connection.commit()
        app.sessions[session_id] = {"session_id": session_id, "user_id": user_id}

        get_status_headers = {}

        def get_start_response(status, headers):
            get_status_headers["status"] = status
            get_status_headers["headers"] = dict(headers)

        get_response = app(
            {
                "PATH_INFO": "/seller/register",
                "REQUEST_METHOD": "GET",
                "CONTENT_LENGTH": "0",
                "HTTP_COOKIE": f"session_id={session_id}",
                "wsgi.input": BytesIO(b""),
            },
            get_start_response,
        )

        self.assertEqual(get_status_headers["status"], "200 OK")
        self.assertIn("Confirm your seller profile", b"".join(get_response).decode("utf-8"))

        post_status_headers = {}

        def post_start_response(status, headers):
            post_status_headers["status"] = status
            post_status_headers["headers"] = dict(headers)

        body = b"confirm_seller=yes"
        response = app(
            {
                "PATH_INFO": "/seller/register",
                "REQUEST_METHOD": "POST",
                "CONTENT_LENGTH": str(len(body)),
                "HTTP_COOKIE": f"session_id={session_id}",
                "wsgi.input": BytesIO(body),
            },
            post_start_response,
        )

        with database.get_connection() as connection:
            seller = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        self.assertEqual(post_status_headers["status"], "302 Found")
        self.assertEqual(post_status_headers["headers"]["Location"], "/seller")
        self.assertEqual(response, [b""])
        self.assertEqual(seller["role"], "seller")

    def test_seller_can_update_order_status_for_owned_product(self) -> None:
        with database.get_connection() as connection:
            auth = AuthService(connection)
            seller_id = auth.register("Order Seller", "orderseller@example.com", "secret1", "secret1")
            connection.commit()
            auth.register_seller(seller_id)
            seller_service = SellerService(connection)
            product_id = seller_service.create_listing(
                seller_id,
                {
                    "title": "Seller Denim Vest",
                    "brand": "Reworked",
                    "category": "Outerwear",
                    "size": "M",
                    "condition_label": "Very Good",
                    "price": "32.00",
                    "description": "A reworked denim vest from a seller closet.",
                    "image_url": "https://example.com/vest.jpg",
                    "stock": "2",
                },
            )

            owner_key = "guest:seller-order"
            cart = CartService(connection)
            cart.add_item(owner_key, product_id)
            order_id = CheckoutService(connection).checkout(
                owner_key=owner_key,
                user_id=None,
                guest_name="Order Guest",
                guest_email="orderguest@example.com",
                shipping_address="12 Main Street",
                city="Cairo",
                country="Egypt",
                payment_method="cod",
            )
            seller_service.update_order_status(seller_id, order_id, "shipped")
            order = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

        self.assertEqual(order["status"], "shipped")


if __name__ == "__main__":
    unittest.main()
