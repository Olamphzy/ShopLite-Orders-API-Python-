import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ..auth import User, current_user
from ..errors import AppError

router = APIRouter(prefix="/api/orders")


def order_summary(row: dict) -> dict:
    return {"id": row["id"], "status": row["status"], "total_cents": row["total_cents"], "created_at": row["created_at"]}


def load_order(conn: sqlite3.Connection, order_id: int, user_id: int | None = None) -> dict | None:
    if user_id is None:
        order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    else:
        order = conn.execute("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)).fetchone()
    if order is None:
        return None
    items = conn.execute(
        """SELECT order_items.product_id, products.name, order_items.quantity, order_items.price_cents
             FROM order_items JOIN products ON products.id = order_items.product_id
            WHERE order_items.order_id = ?
            ORDER BY order_items.id""",
        (order_id,),
    ).fetchall()
    return {**order_summary(dict(order)), "items": [dict(item) for item in items]}


@router.get("")
async def list_orders(
    request: Request,
    user: User = Depends(current_user),
    page: Annotated[int, Query(gt=0)] = 1,
    limit: Annotated[int, Query(gt=0, le=50)] = 10,
):
    db = request.app.state.services.db
    total = db.fetch_one("SELECT COUNT(*) AS total FROM orders WHERE user_id = ?", (user.id,))["total"]
    offset = (page - 1) * limit
    rows = db.fetch_all(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (user.id, limit, offset),
    )
    return {"page": page, "limit": limit, "total": total, "items": [order_summary(row) for row in rows]}


@router.get("/{order_id}")
async def get_order(order_id: int, request: Request, user: User = Depends(current_user)):
    conn = request.app.state.services.db.connect()
    try:
        order = load_order(conn, order_id, user.id)
    finally:
        conn.close()
    if order is None:
        raise AppError(404, "NOT_FOUND", "Order not found")
    return order
