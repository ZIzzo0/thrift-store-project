from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from thrift_store.app import create_app
from thrift_store import database
from thrift_store.services import AuthService, CartService, CheckoutService


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
            user_id = auth.register("Test User", "test@example.com", "secret1")
            connection.commit()
            user = auth.login("test@example.com", "secret1")
        self.assertEqual(user_id, user["id"])

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


if __name__ == "__main__":
    unittest.main()
