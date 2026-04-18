# ReThread

This project is an online thrift store built with a simple layered Python architecture:

- Presentation layer: WSGI routes and HTML views
- Business layer: authentication, catalog, cart, and checkout services
- Data layer: SQLite repositories and seeded thrift products

## Features covered

- `S-02` User registration
- `S-03` User login
- `S-04` Browse products
- `S-07` View product details
- `S-08` Add item to cart
- `S-09` Remove item from cart
- `S-10a` Checkout shipping and calculation
- `S-10b` Checkout order confirmation
- `S-01` Guest checkout

## Run locally

```bash
python run.py
```

Then open `http://127.0.0.1:8000`.

## Run tests

```bash
python tests.py
```
