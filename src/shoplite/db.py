import contextlib
import os
import sqlite3
from typing import Iterator, NamedTuple

from .auth import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders (user_id, created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    amount_cents INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    order_id INTEGER REFERENCES orders(id),
    template TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    cart_hash TEXT NOT NULL,
    order_id INTEGER REFERENCES orders(id),
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(user_id, key)
);
"""

USERS = [
    ("alice@shoplite.test", "Alice"),
    ("bob@shoplite.test", "Bob"),
    ("carol@shoplite.test", "Carol"),
    ("dave@shoplite.test", "Dave"),
    ("erin@shoplite.test", "Erin"),
]

PRODUCTS = [
    ("Water Bottle", 19.99, 50),
    ("Backpack", 49.99, 25),
    ("Desk Lamp", 34.99, 10),
    ("Chef's Knife", 59.99, 8),
    ("Notebook", 4.35, 100),
    ("Headphones", 129.99, 5),
    ("Coffee Mug", 12.99, 40),
    ("Running Shoes", 89.99, 12),
    ("Sticker Pack", 0.29, 500),
    ("Pencil", 1.15, 300),
    ("USB Cable", 8.95, 80),
    ("Phone Case", 14.99, 60),
    ("Mouse Pad", 9.99, 45),
    ("Water Filter", 24.95, 30),
    ("Yoga Mat", 29.99, 20),
    ("Sunglasses", 39.95, 15),
    ("Wall Clock", 22.49, 18),
    ("Tea Sampler", 16.85, 35),
    ("Plant Pot", 11.15, 25),
    ("Candle", 7.85, 70),
    ("Socks", 5.55, 90),
    ("Umbrella", 18.45, 22),
    ("Scarf", 26.35, 16),
    ("Keychain", 2.95, 150),
]

DEFAULT_PASSWORD = "password123"


class ExecuteResult(NamedTuple):
    lastrowid: int | None
    rowcount: int


class Database:
    """
    A SQLite database file. Every call opens its own connection, so the class is safe to use
    from any thread.

    `transaction()` takes SQLite's write lock (BEGIN IMMEDIATE) until the block exits: commit on
    success, rollback on exception. Do not `await` inside a transaction block. Other requests on
    the event loop would block waiting for the lock while the coroutine holding it cannot resume.
    """

    def __init__(self, path: str):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def fetch_one(self, sql: str, params: tuple = (), conn: sqlite3.Connection | None = None) -> dict | None:
        if conn is None:
            conn = self.connect()
            close = True
        else:
            close = False
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            if close:
                conn.close()

    def fetch_all(self, sql: str, params: tuple = (), conn: sqlite3.Connection | None = None) -> list[dict]:
        if conn is None:
            conn = self.connect()
            close = True
        else:
            close = False
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            if close:
                conn.close()

    def execute(self, sql: str, params: tuple = (), conn: sqlite3.Connection | None = None) -> ExecuteResult:
        if conn is None:
            conn = self.connect()
            close = True
        else:
            close = False
        try:
            cursor = conn.execute(sql, params)
            return ExecuteResult(cursor.lastrowid, cursor.rowcount)
        finally:
            if close:
                conn.close()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()


def init_database(path: str, reset: bool = False) -> Database:
    """Creates the schema, and seeds users and products if the database is empty."""
    if reset:
        for suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(FileNotFoundError):
                os.remove(path + suffix)

    db = Database(path)
    conn = db.connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.execute("BEGIN")
            conn.executemany(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                [(email, name, hash_password(DEFAULT_PASSWORD)) for email, name in USERS],
            )
            conn.executemany("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", PRODUCTS)
            conn.execute("COMMIT")
    finally:
        conn.close()
    return db
