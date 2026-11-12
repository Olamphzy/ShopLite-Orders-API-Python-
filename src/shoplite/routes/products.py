from fastapi import APIRouter, Request

from ..money import to_cents

router = APIRouter(prefix="/api")


def product_out(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "price_cents": to_cents(row["price"]), "stock": row["stock"]}


@router.get("/products")
async def list_products(request: Request, q: str | None = None):
    services = request.app.state.services
    q = (q or "").strip()
    cached = services.product_cache.get(q)
    if cached is not None:
        return cached

    if q:
        rows = services.db.fetch_all("SELECT * FROM products WHERE LOWER(name) LIKE LOWER(?) ORDER BY id", (f"%{q}%",))
    else:
        rows = services.db.fetch_all("SELECT * FROM products ORDER BY id")
    body = {"items": [product_out(row) for row in rows]}
    services.product_cache.set(q, body)
    return body
