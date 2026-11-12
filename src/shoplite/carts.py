import threading


class Cart:
    def __init__(self, user_id: int, items: dict | None = None):
        self.user_id = user_id
        # product_id -> quantity
        self.items = {} if items is None else items


class CartStore:
    """In-memory carts, one per user."""

    def __init__(self):
        self._carts: dict[int, Cart] = {}
        self._lock = threading.Lock()

    def get(self, user_id: int) -> Cart:
        with self._lock:
            if user_id not in self._carts:
                self._carts[user_id] = Cart(user_id)
            return self._carts[user_id]
