from __future__ import annotations

from html import escape

from thrift_store.services import format_money


def render_layout(*, title: str, body: str, current_user=None, cart_count: int = 0, flash: str = "") -> bytes:
    auth_links = (
        f"<span class='welcome'>Signed in as {escape(current_user['full_name'])}</span><a href='/logout'>Logout</a>"
        if current_user
        else "<a href='/login'>Login</a><a href='/register'>Register</a>"
    )
    flash_html = f"<div class='flash'>{escape(flash)}</div>" if flash else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header class="site-header">
    <div class="brand-block">
      <a class="brand" href="/">ReThread</a>
      <p class="tagline">A curated online thrift store with layered architecture.</p>
    </div>
    <nav class="nav-links">
      <a href="/">Browse</a>
      <a href="/cart">Cart ({cart_count})</a>
      {auth_links}
    </nav>
  </header>
  <main class="page-shell">
    {flash_html}
    {body}
  </main>
</body>
</html>
"""
    return page.encode("utf-8")


def render_home(products, cart_count: int, current_user=None, flash: str = "") -> bytes:
    cards = []
    for product in products:
        cards.append(
            f"""
            <article class="product-card">
              <a href="/products/{product['id']}"><img src="{escape(product['image_url'])}" alt="{escape(product['title'])}"></a>
              <div class="product-meta">
                <p class="eyebrow">{escape(product['brand'])} · {escape(product['category'])}</p>
                <h2><a href="/products/{product['id']}">{escape(product['title'])}</a></h2>
                <p class="details">Size {escape(product['size'])} · {escape(product['condition_label'])}</p>
                <div class="price-row">
                  <strong>{format_money(product['price_cents'])}</strong>
                  <form method="post" action="/cart/add">
                    <input type="hidden" name="product_id" value="{product['id']}">
                    <button type="submit">Add to cart</button>
                  </form>
                </div>
              </div>
            </article>
            """
        )

    body = f"""
    <section class="hero">
      <div>
        <p class="hero-kicker">Online thrift store</p>
        <h1>Browse unique second-hand pieces and complete a purchase in one flow.</h1>
        <p class="hero-copy">Browse products, view details, manage your cart, and complete checkout with or without an account.</p>
      </div>
    </section>
    <section class="catalog-grid">
      {''.join(cards)}
    </section>
    """
    return render_layout(title="Browse Products", body=body, current_user=current_user, cart_count=cart_count, flash=flash)


def render_product(product, cart_count: int, current_user=None, flash: str = "") -> bytes:
    body = f"""
    <section class="detail-grid">
      <img class="detail-image" src="{escape(product['image_url'])}" alt="{escape(product['title'])}">
      <div class="detail-panel">
        <p class="eyebrow">{escape(product['brand'])} · {escape(product['category'])}</p>
        <h1>{escape(product['title'])}</h1>
        <p class="details">Size {escape(product['size'])} · {escape(product['condition_label'])}</p>
        <p class="price-lg">{format_money(product['price_cents'])}</p>
        <p class="description">{escape(product['description'])}</p>
        <form method="post" action="/cart/add" class="stack-form">
          <input type="hidden" name="product_id" value="{product['id']}">
          <button type="submit">Add item to cart</button>
        </form>
        <a class="text-link" href="/">Back to product listing</a>
      </div>
    </section>
    """
    return render_layout(title=product["title"], body=body, current_user=current_user, cart_count=cart_count, flash=flash)


def render_auth_page(*, page_title: str, heading: str, action: str, cart_count: int, flash: str = "", current_user=None) -> bytes:
    extra_name = "<label>Full name<input type='text' name='full_name' required></label>" if action == "/register" else ""
    button = "Create account" if action == "/register" else "Sign in"
    helper = (
        "Already have an account? <a href='/login'>Login here</a>."
        if action == "/register"
        else "Need an account? <a href='/register'>Register here</a>."
    )
    body = f"""
    <section class="form-card auth-card">
      <h1>{escape(heading)}</h1>
      <p class="muted">Use an account for a faster checkout, or keep browsing as a guest.</p>
      <form method="post" action="{action}" class="stack-form">
        {extra_name}
        <label>Email<input type="email" name="email" required></label>
        <label>Password<input type="password" name="password" required></label>
        <button type="submit">{button}</button>
      </form>
      <p class="muted">{helper}</p>
    </section>
    """
    return render_layout(title=page_title, body=body, current_user=current_user, cart_count=cart_count, flash=flash)


def render_cart(summary, cart_count: int, current_user=None, flash: str = "") -> bytes:
    if summary.items:
        rows = []
        for item in summary.items:
            rows.append(
                f"""
                <article class="cart-row">
                  <img src="{escape(item['image_url'])}" alt="{escape(item['title'])}">
                  <div class="cart-copy">
                    <h2>{escape(item['title'])}</h2>
                    <p>{escape(item['brand'])}</p>
                    <p>Qty {item['quantity']}</p>
                    <strong>{format_money(item['price_cents'] * item['quantity'])}</strong>
                  </div>
                  <form method="post" action="/cart/remove">
                    <input type="hidden" name="product_id" value="{item['product_id']}">
                    <button class="secondary" type="submit">Remove</button>
                  </form>
                </article>
                """
            )
        content = f"""
        <section class="cart-layout">
          <div class="cart-list">{''.join(rows)}</div>
          <aside class="summary-card">
            <h2>Order summary</h2>
            <p><span>Subtotal</span><strong>{format_money(summary.subtotal_cents)}</strong></p>
            <p><span>Shipping</span><strong>{format_money(summary.shipping_cents)}</strong></p>
            <p class="summary-total"><span>Total</span><strong>{format_money(summary.total_cents)}</strong></p>
            <a class="checkout-link" href="/checkout">Proceed to checkout</a>
          </aside>
        </section>
        """
    else:
        content = """
        <section class="form-card empty-card">
          <h1>Your cart is empty</h1>
          <p class="muted">Add a few thrift finds to continue to checkout.</p>
          <a class="checkout-link" href="/">Back to browse</a>
        </section>
        """
    return render_layout(title="Your Cart", body=content, current_user=current_user, cart_count=cart_count, flash=flash)


def render_checkout(summary, current_user=None, flash: str = "") -> bytes:
    name_field = (
        ""
        if current_user
        else "<label>Guest name<input type='text' name='guest_name' required></label>"
        "<label>Guest email<input type='email' name='guest_email' required></label>"
    )
    account_note = (
        f"<p class='muted'>Checking out as {escape(current_user['full_name'])}.</p>"
        if current_user
        else "<p class='muted'>Guest checkout is available.</p>"
    )
    body = f"""
    <section class="checkout-layout">
      <form method="post" action="/checkout" class="form-card stack-form">
        <h1>Checkout</h1>
        {account_note}
        {name_field}
        <label>Shipping address<input type="text" name="shipping_address" required></label>
        <label>City<input type="text" name="city" required></label>
        <label>Country<input type="text" name="country" required value="Egypt"></label>
        <label>Payment method
          <select name="payment_method">
            <option value="card">Card</option>
            <option value="cod">Cash on Delivery</option>
          </select>
        </label>
        <button type="submit">Place order</button>
      </form>
      <aside class="summary-card">
        <h2>Shipping & total</h2>
        <p><span>Items</span><strong>{summary.item_count}</strong></p>
        <p><span>Subtotal</span><strong>{format_money(summary.subtotal_cents)}</strong></p>
        <p><span>Shipping</span><strong>{format_money(summary.shipping_cents)}</strong></p>
        <p class="summary-total"><span>Total</span><strong>{format_money(summary.total_cents)}</strong></p>
      </aside>
    </section>
    """
    return render_layout(title="Checkout", body=body, current_user=current_user, cart_count=summary.item_count, flash=flash)


def render_order_confirmation(order, items, current_user=None) -> bytes:
    guest_line = ""
    if order["guest_name"]:
        guest_line = f"<p class='muted'>Guest order for {escape(order['guest_name'])} ({escape(order['guest_email'])})</p>"
    line_items = "".join(
        f"<li>{escape(item['title'])} × {item['quantity']} <strong>{format_money(item['unit_price_cents'] * item['quantity'])}</strong></li>"
        for item in items
    )
    body = f"""
    <section class="form-card confirmation-card">
      <p class="hero-kicker">Order confirmed</p>
      <h1>Thanks for shopping with ReThread.</h1>
      {guest_line}
      <p>Your order #{order['id']} has been created successfully.</p>
      <ul class="confirmation-list">{line_items}</ul>
      <div class="summary-card summary-inline">
        <p><span>Subtotal</span><strong>{format_money(order['subtotal_cents'])}</strong></p>
        <p><span>Shipping</span><strong>{format_money(order['shipping_cents'])}</strong></p>
        <p class="summary-total"><span>Total</span><strong>{format_money(order['total_cents'])}</strong></p>
      </div>
      <a class="checkout-link" href="/">Continue browsing</a>
    </section>
    """
    return render_layout(title="Order Confirmation", body=body, current_user=current_user, cart_count=0)
