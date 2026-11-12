import asyncio
import time

from shop_testkit import (  # noqa: F401  (make_shop is a fixture)
    BACKPACK,
    COFFEE_MUG,
    DESK_LAMP,
    HEADPHONES,
    NOTEBOOK,
    PENCIL,
    RUNNING_SHOES,
    USERS,
    WATER_BOTTLE,
    make_shop,
)


# ---------------- Task 1 ----------------

def test_task1_pagination_page_1_is_the_most_recent(make_shop):
    shop = make_shop()
    ids = shop.insert_orders(USERS[0], 12)
    token = shop.login()

    body = shop.request("GET", "/api/orders?page=1", token).json()

    assert {k: body[k] for k in ("page", "limit", "total")} == {"page": 1, "limit": 10, "total": 12}
    assert body["items"][0]["id"] == ids[-1]
    assert len(body["items"]) == 10


def test_task1_carts_are_not_shared(make_shop):
    shop = make_shop()
    erin = shop.login(USERS[4])
    shop.add_to_cart(erin, PENCIL, 2)

    bob = shop.login(USERS[1])

    assert shop.request("GET", "/api/cart", bob).json()["items"] == []


def test_task1_checkout_does_not_freeze_the_api(make_shop):
    shop = make_shop(email_delay=0.6)
    token = shop.login()
    shop.add_to_cart(token, NOTEBOOK, 1)

    async def scenario():
        started = time.monotonic()
        checkout = asyncio.ensure_future(shop.acheckout(token))
        await asyncio.sleep(0.05)
        await shop.arequest("GET", "/api/products")
        elapsed = time.monotonic() - started
        await checkout
        return elapsed

    assert shop.run(scenario()) < 0.4


# ---------------- Task 2 ----------------

def test_task2_users_cannot_read_each_others_orders(make_shop):
    shop = make_shop()
    bob, carol = shop.login(USERS[1]), shop.login(USERS[2])
    order = shop.buy(bob, {COFFEE_MUG: 1})

    assert shop.request("GET", f"/api/orders/{order.json()['id']}", carol).status_code == 404


def test_task2_search_is_not_interpreted_as_sql(make_shop):
    shop = make_shop()

    res = shop.run(shop.client.get("/api/products", params={"q": "x' OR 1=1 --"}))

    assert res.status_code == 200
    assert res.json()["items"] == []


# ---------------- Task 3 ----------------

def test_task3_failed_checkout_writes_nothing(make_shop):
    shop = make_shop()
    token = shop.login()
    shop.add_to_cart(token, WATER_BOTTLE, 1)
    shop.add_to_cart(token, RUNNING_SHOES, 1)
    shop.set_stock(RUNNING_SHOES, 0)

    assert shop.checkout(token).status_code == 409
    assert shop.counts() == {"orders": 0, "order_items": 0, "invoices": 0, "emails": 0}
    assert shop.stock(WATER_BOTTLE) == 50


def test_task3_last_unit_is_sold_once(make_shop):
    shop = make_shop(payment_delay=0.05)
    shop.set_stock(DESK_LAMP, 1)
    tokens = [shop.login(u) for u in USERS[:2]]
    for t in tokens:
        shop.add_to_cart(t, DESK_LAMP, 1)

    results = shop.gather(*(shop.acheckout(t) for t in tokens))

    assert sorted(r.status_code for r in results) == [201, 409]


def test_task3_declined_payment_leaves_no_order(make_shop):
    shop = make_shop(decline=True)
    token = shop.login()

    assert shop.buy(token, {HEADPHONES: 1}).status_code == 402
    assert shop.count("orders") == 0


def test_task3_invoice_is_exact(make_shop):
    shop = make_shop()
    token = shop.login()

    res = shop.buy(token, {WATER_BOTTLE: 3})

    assert res.json()["total_cents"] == 5997


# ---------------- Task 4 ----------------

def test_task4_retry_with_same_key_returns_same_order(make_shop):
    shop = make_shop()
    token = shop.login()

    first = shop.buy(token, {WATER_BOTTLE: 1}, key="retry-example")
    second = shop.checkout(token, key="retry-example")

    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert shop.count("orders") == 1


def test_task4_key_reused_for_a_different_cart_returns_422(make_shop):
    shop = make_shop()
    token = shop.login()
    shop.buy(token, {WATER_BOTTLE: 1}, key="reuse-example")

    shop.add_to_cart(token, BACKPACK, 1)

    assert shop.checkout(token, key="reuse-example").status_code == 422


# ---------------- Task 5 ----------------

def test_task5_invalid_quantity_uses_the_error_format(make_shop):
    shop = make_shop()
    token = shop.login()

    res = shop.request("POST", "/api/cart/items", token, json={"product_id": BACKPACK, "quantity": 0})

    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"
    assert "quantity" in body["error"]["fields"]


def test_task5_login_is_rate_limited_after_5_failures(make_shop):
    shop = make_shop()
    for _ in range(5):
        shop.request("POST", "/api/auth/login", json={"email": USERS[4], "password": "wrong"})

    res = shop.request("POST", "/api/auth/login", json={"email": USERS[4], "password": "wrong"})

    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0
