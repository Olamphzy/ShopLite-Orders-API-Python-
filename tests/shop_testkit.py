# IMPORTANT ! DO NOT MODIFY THIS FILE
# Shared helpers for the tests: a fresh app per test, fake external services and a controllable clock.
import asyncio
import sqlite3
import time

import httpx
import pytest

PASSWORD = "password123"
USERS = ["alice@shoplite.test", "bob@shoplite.test", "carol@shoplite.test", "dave@shoplite.test", "erin@shoplite.test"]

WATER_BOTTLE, BACKPACK, DESK_LAMP, CHEFS_KNIFE, NOTEBOOK, HEADPHONES, COFFEE_MUG, RUNNING_SHOES = range(1, 9)
STICKER_PACK, PENCIL, USB_CABLE = 9, 10, 11
PRODUCT_COUNT = 24


class FakeClock:
    def __init__(self, start: float = 1_768_478_400.0):
        self.current = start

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class FakePayments:
    def __init__(self, delay: float = 0.0, decline: bool = False):
        self.delay = delay
        self.decline = decline
        self.charges: list[dict] = []

    async def charge(self, amount_cents: int, reference: str) -> dict:
        from shoplite.payments import PaymentDeclinedError

        await asyncio.sleep(self.delay)
        if self.decline:
            raise PaymentDeclinedError("Card declined")
        self.charges.append({"amount_cents": amount_cents, "reference": reference})
        return {"id": f"ch_test_{len(self.charges)}", "amount_cents": amount_cents, "reference": reference}


class FakeEmail:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.sent: list[dict] = []

    def send(self, to: str, subject: str, body: str) -> None:
        time.sleep(self.delay)  # blocking, like the real SDK
        self.sent.append({"to": to, "subject": subject, "body": body})


class Shop:
    """A ShopLite app built through create_app(), with sync and async request helpers."""

    def __init__(self, db_path, payment_delay=0.0, decline=False, email_delay=0.0, loop=None):
        from shoplite.app import create_app

        self.db_path = str(db_path)
        self.clock = FakeClock()
        self.payments = FakePayments(payment_delay, decline)
        self.email = FakeEmail(email_delay)
        self.app = create_app(self.db_path, payments=self.payments, email_client=self.email, clock=self.clock.now)
        self.loop = loop or asyncio.new_event_loop()
        self.owns_loop = loop is None
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False), base_url="http://shop.test"
        )

    # --- requests ---
    async def arequest(self, method, path, token=None, json=None, headers=None) -> httpx.Response:
        headers = dict(headers or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await self.client.request(method, path, json=json, headers=headers)

    def request(self, method, path, token=None, json=None, headers=None) -> httpx.Response:
        return self.run(self.arequest(method, path, token, json, headers))

    def run(self, coro):
        return self.loop.run_until_complete(coro)

    def gather(self, *coros) -> list:
        async def _all():
            return await asyncio.gather(*coros)

        return self.run(_all())

    def login(self, email=USERS[0], password=PASSWORD) -> str:
        res = self.request("POST", "/api/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, f"login failed for {email}: {res.status_code} {res.text}"
        return res.json()["token"]

    def add_to_cart(self, token, product_id, quantity=1) -> httpx.Response:
        return self.request("POST", "/api/cart/items", token, json={"product_id": product_id, "quantity": quantity})

    def acheckout(self, token, key=None):
        return self.arequest("POST", "/api/checkout", token, headers={"Idempotency-Key": key} if key else None)

    def checkout(self, token, key=None) -> httpx.Response:
        return self.run(self.acheckout(token, key))

    def buy(self, token, items, key=None) -> httpx.Response:
        """Fills the cart with {product_id: quantity} and checks out."""
        for product_id, quantity in items.items():
            res = self.add_to_cart(token, product_id, quantity)
            assert res.status_code == 200, f"add to cart failed: {res.status_code} {res.text}"
        return self.checkout(token, key)

    # --- direct database access ---
    def sql(self, query, params=()) -> list[dict]:
        conn = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
        finally:
            conn.close()

    def count(self, table) -> int:
        return self.sql(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]

    def counts(self) -> dict:
        return {t: self.count(t) for t in ("orders", "order_items", "invoices", "emails")}

    def stock(self, product_id) -> int:
        return self.sql("SELECT stock FROM products WHERE id = ?", (product_id,))[0]["stock"]

    def set_stock(self, product_id, stock) -> None:
        self.sql("UPDATE products SET stock = ? WHERE id = ?", (stock, product_id))

    def user_id(self, email) -> int:
        return self.sql("SELECT id FROM users WHERE email = ?", (email,))[0]["id"]

    def insert_orders(self, email, n) -> list[int]:
        """Inserts n paid orders, oldest first, one minute apart. Returns their ids oldest first."""
        uid = self.user_id(email)
        base = self.clock.now() - n * 60
        ids = []
        for i in range(n):
            self.sql(
                "INSERT INTO orders (user_id, status, total_cents, created_at) VALUES (?, 'paid', ?, ?)",
                (uid, 1000 + i, base + i * 60),
            )
            ids.append(self.sql("SELECT MAX(id) AS id FROM orders")[0]["id"])
        return ids

    def close(self) -> None:
        self.run(self.client.aclose())
        if self.owns_loop:
            self.loop.close()


@pytest.fixture
def make_shop(tmp_path):
    shops = []

    def _make(**kwargs) -> Shop:
        kwargs.setdefault("db_path", tmp_path / "shoplite.db")
        if shops and "loop" not in kwargs:
            kwargs["loop"] = shops[0].loop
        shop = Shop(**kwargs)
        shops.append(shop)
        return shop

    yield _make
    for shop in reversed(shops):
        shop.close()
