import time
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import FastAPI

from .cache import ProductCache
from .carts import CartStore
from .db import Database, init_database
from .emailer import EmailClient
from .errors import register_error_handlers
from .payments import PaymentGateway
from .routes import auth, cart, checkout, orders, products


@dataclass
class Services:
    db: Database
    payments: Any
    email: Any
    clock: Callable[[], float]
    carts: CartStore
    product_cache: ProductCache
    login_failures: dict[str, list[float]] = field(default_factory=dict)


def create_app(
    db_path: str,
    payments: Any = None,
    email_client: Any = None,
    clock: Callable[[], float] | None = None,
) -> FastAPI:
    """
    Builds the API. Tests call this directly, so keep the signature.
    `clock` returns the current time in seconds; use it for all time-based logic.
    """
    clock = clock or time.time
    app = FastAPI(title="ShopLite")
    app.state.services = Services(
        db=init_database(db_path),
        payments=payments or PaymentGateway(),
        email=email_client or EmailClient(),
        clock=clock,
        carts=CartStore(),
        product_cache=ProductCache(clock),
        login_failures={},
    )
    register_error_handlers(app)
    for module in (auth, products, cart, orders, checkout):
        app.include_router(module.router)
    return app
