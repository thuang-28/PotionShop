from enum import Enum

import sqlalchemy
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)


class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"


class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"


@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku,
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int


@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Shares the customers that visited the store on that tick. Not all
    customers end up purchasing because they may not like what they see
    in the current catalog.
    """
    print(customers)

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """Creates a new cart for a specific customer."""
    with db.engine.begin() as connection:
        cart_id = connection.execute(
            sqlalchemy.text(
                """
                INSERT INTO carts (customer_name, customer_class, level)
                        VALUES (:name, :class, :level)
                    RETURNING carts.id
                """
            ),
            {
                "name": new_cart.customer_name,
                "class": new_cart.character_class,
                "level": new_cart.level,
            },
        ).scalar_one()
    print(f"[Log] New cart created (ID {cart_id}) for", new_cart)
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """Updates the quantity of a specific item in a cart."""
    print(f"[Log] Cart item updated (ID {cart_id}): {item_sku} (x{cart_item.quantity})")
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                """
                INSERT INTO cart_items (cart_id, sku, quantity)
                     VALUES (:id, :sku, :quantity)
                ON CONFLICT (cart_id, sku)
                  DO UPDATE
                        SET quantity = :quantity
                """
            ),
            {"id": cart_id, "sku": item_sku, "quantity": cart_item.quantity},
        )
    return "OK"


class CartCheckout(BaseModel):
    payment: str


@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """Handles the checkout process for a specific cart."""
    print(
        f"[Log] Checked out (Cart ID {cart_id}) w/ payment method '{cart_checkout.payment}':",
        checkout,
    )
    with db.engine.begin() as connection:
        total_price = connection.execute(
            sqlalchemy.text(
                """
                INSERT INTO potion_records (sku, qty_change)
                SELECT sku, quantity * -1 FROM cart_items
                 WHERE cart_id = :id;
                INSERT INTO gold_records (change_in_gold)
                SELECT SUM(potion_index.price * cart_items.quantity)
                  FROM potion_index JOIN cart_items
                    ON potion_index.sku = cart_items.sku AND cart_id = :cart_id
                RETURNING change_in_gold;
                """
            ),
            {"cart_id": cart_id},
        ).scalar_one()
        total_potions_bought = connection.execute(
            sqlalchemy.text(
                """
                SELECT SUM(cart_items.quantity) FROM cart_items
                 WHERE cart_id = :cart_id
                """
            ),
            {"cart_id": cart_id},
        ).scalar_one()
    checkout = {
        "total_potions_bought": total_potions_bought,
        "total_gold_paid": total_price,
    }
    return checkout
