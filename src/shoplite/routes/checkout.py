import threading
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Request

from ..auth import User, current_user
from ..errors import AppError
from ..money import to_cents
from ..payments import PaymentDeclinedError
from .orders import load_order

router = APIRouter(prefix="/api")


def cart_hash(items: dict[int, int]) -> str:
    digest = sha256()
    for product_id, quantity in sorted(items.items()):
        digest.update(f"{product_id}:{quantity};".encode())
    return digest.hexdigest()


@router.post("/checkout", status_code=201)
async def checkout(
    request: Request,
    user: User = Depends(current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    services = request.app.state.services
    cart = services.carts.get(user.id)
    key = idempotency_key.strip() if idempotency_key else None

    if key is not None:
        key_hash = cart_hash(cart.items)
        record = services.db.fetch_one(
            "SELECT * FROM idempotency_keys WHERE user_id = ? AND key = ?",
            (user.id, key),
        )
        if record is not None:
            if record["status"] == "processing":
                raise AppError(409, "IDEMPOTENCY_KEY_IN_PROGRESS", "Idempotency key is already being processed")
            if record["order_id"] is not None:
                if (not cart.items) or (record["cart_hash"] == key_hash):
                    conn = services.db.connect()
                    try:
                        order = load_order(conn, record["order_id"], user.id)
                        if order is not None:
                            return order
                    finally:
                        conn.close()
                raise AppError(422, "IDEMPOTENCY_KEY_REUSED", "Idempotency key already used for a different cart")
            if record["cart_hash"] != key_hash:
                raise AppError(422, "IDEMPOTENCY_KEY_REUSED", "Idempotency key already used for a different cart")
        services.db.execute(
            "INSERT INTO idempotency_keys (user_id, key, cart_hash, status, created_at) VALUES (?, ?, ?, 'processing', ?)",
            (user.id, key, key_hash, services.clock()),
        )

    if not cart.items:
        raise AppError(400, "EMPTY_CART", "Your cart is empty")

    try:
        lines = []
        total_cents = 0
        for product_id, quantity in sorted(cart.items.items()):
            product = services.db.fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
            if product is None:
                raise AppError(404, "NOT_FOUND", f"Product {product_id} not found")
            price_cents = to_cents(product["price"])
            lines.append((product, quantity, price_cents))
            total_cents += price_cents * quantity

        try:
            await services.payments.charge(total_cents, reference=f"user-{user.id}-cart-{key or 'checkout'}")
        except PaymentDeclinedError:
            if key is not None:
                services.db.execute("DELETE FROM idempotency_keys WHERE user_id = ? AND key = ?", (user.id, key))
            raise AppError(402, "PAYMENT_DECLINED", "Your card was declined")

        with services.db.transaction() as conn:
            for product, quantity, price_cents in lines:
                current = services.db.fetch_one("SELECT * FROM products WHERE id = ?", (product["id"],), conn)
                if current["stock"] < quantity:
                    raise AppError(409, "OUT_OF_STOCK", f"{product['name']} does not have enough stock")

            now = services.clock()
            order_id = services.db.execute(
                "INSERT INTO orders (user_id, status, total_cents, created_at) VALUES (?, 'pending', ?, ?)",
                (user.id, total_cents, now),
                conn,
            ).lastrowid
            services.db.execute(
                "INSERT INTO emails (user_id, order_id, template, created_at) VALUES (?, ?, 'order_confirmation', ?)",
                (user.id, order_id, now),
                conn,
            )

            for product, quantity, price_cents in lines:
                services.db.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ?",
                    (quantity, product["id"]),
                    conn,
                )
                services.db.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price_cents) VALUES (?, ?, ?, ?)",
                    (order_id, product["id"], quantity, price_cents),
                    conn,
                )

            services.db.execute("UPDATE orders SET status = 'paid' WHERE id = ?", (order_id,), conn)
            services.db.execute(
                "INSERT INTO invoices (order_id, amount_cents, created_at) VALUES (?, ?, ?)",
                (order_id, total_cents, now),
                conn,
            )
            if key is not None:
                services.db.execute(
                    "UPDATE idempotency_keys SET order_id = ?, status = 'succeeded' WHERE user_id = ? AND key = ?",
                    (order_id, user.id, key),
                    conn,
                )
            cart.items.clear()

        threading.Thread(
            target=services.email.send,
            args=(user.email, f"Your ShopLite order #{order_id}", "Thanks for your order!"),
            daemon=True,
        ).start()

        conn = services.db.connect()
        try:
            return load_order(conn, order_id, user.id)
        finally:
            conn.close()
    except AppError:
        if key is not None:
            services.db.execute("DELETE FROM idempotency_keys WHERE user_id = ? AND key = ?", (user.id, key))
        raise
