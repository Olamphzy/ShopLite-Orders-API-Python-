from fastapi import APIRouter, Depends, Request

from ..auth import User, current_user
from ..money import to_cents
from ..schemas import CartItemRequest

router = APIRouter(prefix="/api/cart")


def cart_view(request: Request, user_id: int) -> dict:
    services = request.app.state.services
    cart = services.carts.get(user_id)
    lines = []
    for product_id, quantity in sorted(cart.items.items()):
        product = services.db.fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
        if product is None:
            continue
        price_cents = to_cents(product["price"])
        lines.append(
            {
                "product_id": product_id,
                "name": product["name"],
                "quantity": quantity,
                "price_cents": price_cents,
                "line_total_cents": price_cents * quantity,
            }
        )
    return {"items": lines, "total_cents": sum(line["line_total_cents"] for line in lines)}


@router.get("")
def get_cart(request: Request, user: User = Depends(current_user)):
    return cart_view(request, user.id)


@router.post("/items")
def add_item(body: CartItemRequest, request: Request, user: User = Depends(current_user)):
    cart = request.app.state.services.carts.get(user.id)
    cart.items[body.product_id] = cart.items.get(body.product_id, 0) + body.quantity
    return cart_view(request, user.id)


@router.delete("/items/{product_id}")
def remove_item(product_id: int, request: Request, user: User = Depends(current_user)):
    request.app.state.services.carts.get(user.id).items.pop(product_id, None)
    return cart_view(request, user.id)
