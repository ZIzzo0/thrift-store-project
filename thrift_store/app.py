from __future__ import annotations

import secrets
from http import cookies
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from thrift_store.database import get_connection, initialize_database
from thrift_store.repositories import OrderRepository, UserRepository
from thrift_store.services import AuthService, CartService, CatalogService, CheckoutService
from thrift_store.views import (
    render_auth_page,
    render_cart,
    render_checkout,
    render_home,
    render_order_confirmation,
    render_product,
)


STATIC_PATH = Path(__file__).resolve().parent.parent / "static" / "style.css"


class ThriftStoreApp:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}

    def serve(self, host: str = "127.0.0.1", port: int = 8000) -> None:
        print(f"Serving ReThread on http://{host}:{port}")
        with make_server(host, port, self) as server:
            server.serve_forever()

    def __call__(self, environ, start_response):
        initialize_database()
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET").upper()
        context = self._get_session_context(environ)

        try:
            if path == "/static/style.css":
                return self._serve_static(start_response)
            if path == "/" and method == "GET":
                return self._home(start_response, context)
            if path.startswith("/products/") and method == "GET":
                return self._product_detail(path, start_response, context)
            if path == "/register" and method == "GET":
                body = render_auth_page(
                    page_title="Register",
                    heading="Create your account",
                    action="/register",
                    cart_count=self._cart_count(context),
                    flash=self._consume_flash(context),
                )
                return self._ok(start_response, body, context)
            if path == "/register" and method == "POST":
                return self._register(environ, start_response, context)
            if path == "/login" and method == "GET":
                body = render_auth_page(
                    page_title="Login",
                    heading="Welcome back",
                    action="/login",
                    cart_count=self._cart_count(context),
                    flash=self._consume_flash(context),
                )
                return self._ok(start_response, body, context)
            if path == "/login" and method == "POST":
                return self._login(environ, start_response, context)
            if path == "/logout" and method == "GET":
                return self._logout(start_response, context)
            if path == "/cart" and method == "GET":
                return self._cart(start_response, context)
            if path == "/cart/add" and method == "POST":
                return self._cart_add(environ, start_response, context)
            if path == "/cart/remove" and method == "POST":
                return self._cart_remove(environ, start_response, context)
            if path == "/checkout" and method == "GET":
                return self._checkout_page(start_response, context)
            if path == "/checkout" and method == "POST":
                return self._checkout_submit(environ, start_response, context)
            if path.startswith("/order/") and method == "GET":
                return self._order_confirmation(path, start_response, context)
        except ValueError as error:
            context["flash"] = str(error)
            self.sessions[context["session_id"]] = context
            fallback = environ.get("HTTP_REFERER", "/")
            return self._redirect(start_response, fallback, context)

        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    def _serve_static(self, start_response):
        content = STATIC_PATH.read_bytes()
        start_response("200 OK", [("Content-Type", "text/css; charset=utf-8")])
        return [content]

    def _home(self, start_response, context):
        with get_connection() as connection:
            products = CatalogService(connection).list_products()
            body = render_home(
                products,
                self._cart_count(context),
                current_user=self._current_user(connection, context),
                flash=self._consume_flash(context),
            )
        return self._ok(start_response, body, context)

    def _product_detail(self, path: str, start_response, context):
        product_id = int(path.split("/")[-1])
        with get_connection() as connection:
            product = CatalogService(connection).get_product(product_id)
            body = render_product(
                product,
                self._cart_count(context),
                current_user=self._current_user(connection, context),
                flash=self._consume_flash(context),
            )
        return self._ok(start_response, body, context)

    def _register(self, environ, start_response, context):
        form = self._parse_post(environ)
        with get_connection() as connection:
            user_id = AuthService(connection).register(form.get("full_name", ""), form.get("email", ""), form.get("password", ""))
            connection.commit()
        context["user_id"] = user_id
        context["flash"] = "Registration complete. You are now signed in."
        self.sessions[context["session_id"]] = context
        return self._redirect(start_response, "/", context)

    def _login(self, environ, start_response, context):
        form = self._parse_post(environ)
        with get_connection() as connection:
            user = AuthService(connection).login(form.get("email", ""), form.get("password", ""))
        context["user_id"] = user["id"]
        context["flash"] = "Login successful."
        self.sessions[context["session_id"]] = context
        return self._redirect(start_response, "/", context)

    def _logout(self, start_response, context):
        context.pop("user_id", None)
        context["flash"] = "You have been logged out."
        self.sessions[context["session_id"]] = context
        return self._redirect(start_response, "/", context)

    def _cart(self, start_response, context):
        with get_connection() as connection:
            summary = CartService(connection).get_summary(self._owner_key(context))
            body = render_cart(
                summary,
                summary.item_count,
                current_user=self._current_user(connection, context),
                flash=self._consume_flash(context),
            )
        return self._ok(start_response, body, context)

    def _cart_add(self, environ, start_response, context):
        form = self._parse_post(environ)
        with get_connection() as connection:
            CartService(connection).add_item(self._owner_key(context), int(form["product_id"]))
        context["flash"] = "Item added to cart."
        self.sessions[context["session_id"]] = context
        return self._redirect(start_response, environ.get("HTTP_REFERER", "/"), context)

    def _cart_remove(self, environ, start_response, context):
        form = self._parse_post(environ)
        with get_connection() as connection:
            CartService(connection).remove_item(self._owner_key(context), int(form["product_id"]))
        context["flash"] = "Item removed from cart."
        self.sessions[context["session_id"]] = context
        return self._redirect(start_response, "/cart", context)

    def _checkout_page(self, start_response, context):
        with get_connection() as connection:
            summary = CartService(connection).get_summary(self._owner_key(context))
            body = render_checkout(
                summary,
                current_user=self._current_user(connection, context),
                flash=self._consume_flash(context),
            )
        return self._ok(start_response, body, context)

    def _checkout_submit(self, environ, start_response, context):
        form = self._parse_post(environ)
        with get_connection() as connection:
            order_id = CheckoutService(connection).checkout(
                owner_key=self._owner_key(context),
                user_id=context.get("user_id"),
                guest_name=form.get("guest_name"),
                guest_email=form.get("guest_email"),
                shipping_address=form.get("shipping_address", ""),
                city=form.get("city", ""),
                country=form.get("country", ""),
                payment_method=form.get("payment_method", ""),
            )
        return self._redirect(start_response, f"/order/{order_id}", context)

    def _order_confirmation(self, path: str, start_response, context):
        order_id = int(path.split("/")[-1])
        with get_connection() as connection:
            orders = OrderRepository(connection)
            order = orders.get_order(order_id)
            items = orders.get_order_items(order_id)
            body = render_order_confirmation(order, items, current_user=self._current_user(connection, context))
        return self._ok(start_response, body, context)

    def _ok(self, start_response, body: bytes, context=None):
        headers = [("Content-Type", "text/html; charset=utf-8")]
        if context:
            headers.append(("Set-Cookie", self._session_cookie(context["session_id"])))
        start_response("200 OK", headers)
        return [body]

    def _redirect(self, start_response, location: str, context):
        headers = [("Location", location), ("Set-Cookie", self._session_cookie(context["session_id"]))]
        start_response("302 Found", headers)
        return [b""]

    def _parse_post(self, environ):
        size = int(environ.get("CONTENT_LENGTH", "0") or "0")
        body = environ["wsgi.input"].read(size)
        raw = parse_qs(body.decode("utf-8"))
        return {key: values[0] for key, values in raw.items()}

    def _get_session_context(self, environ):
        cookie_header = environ.get("HTTP_COOKIE", "")
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        session_id = jar["session_id"].value if "session_id" in jar else secrets.token_hex(16)
        context = self.sessions.get(session_id, {"session_id": session_id})
        context["session_id"] = session_id
        self.sessions[session_id] = context
        return context

    def _session_cookie(self, session_id: str) -> str:
        jar = cookies.SimpleCookie()
        jar["session_id"] = session_id
        jar["session_id"]["path"] = "/"
        jar["session_id"]["httponly"] = True
        return jar.output(header="").strip()

    def _owner_key(self, context) -> str:
        user_id = context.get("user_id")
        return f"user:{user_id}" if user_id else f"guest:{context['session_id']}"

    def _cart_count(self, context) -> int:
        with get_connection() as connection:
            summary = CartService(connection).get_summary(self._owner_key(context))
            return summary.item_count

    def _current_user(self, connection, context):
        if not context.get("user_id"):
            return None
        return UserRepository(connection).find_by_id(context["user_id"])

    def _consume_flash(self, context) -> str:
        flash = context.pop("flash", "")
        self.sessions[context["session_id"]] = context
        return flash


def create_app() -> ThriftStoreApp:
    initialize_database()
    return ThriftStoreApp()
