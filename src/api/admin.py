import sqlalchemy
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)


@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                """
                UPDATE global_inventory
                   SET num_red_ml = 0,
                       num_green_ml = 0,
                       num_blue_ml = 0,
                       num_dark_ml = 0,
                       gold = 100,
                       potion_capacity = 1,
                       ml_capacity = 1;
                DELETE FROM cart_items;
                DELETE FROM carts;
                DELETE FROM customers;
                DELETE FROM potion_inventory;
                """
            )
        )
    print("[Log] Game state has been reset.")
    return "OK"
