from enum import Enum

import sqlalchemy
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)


class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int


@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    total_bottles = sum([potion.quantity for potion in potions_delivered])
    total_ml = sum(
        [potion.potion_type[1] * potion.quantity for potion in potions_delivered]
    )
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                f"UPDATE global_inventory \
                    SET num_green_potions = num_green_potions + {total_bottles}, \
                    num_green_ml = num_green_ml - {total_ml}"
            )
        )
    print(f"potions delivered: {potions_delivered} order_id: {order_id}")

    return "OK"


@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.
    with db.engine.begin() as connection:
        result = connection.execute(
            sqlalchemy.text("SELECT num_green_ml FROM global_inventory")
        )
        available_ml = result.first().num_green_ml
    num_mixable_potions = int(available_ml / 100)
    if num_mixable_potions > 0:
        return [
            {
                "potion_type": [0, 100, 0, 0],
                "quantity": num_mixable_potions,
            }
        ]
    return []


if __name__ == "__main__":
    print(get_bottle_plan())
