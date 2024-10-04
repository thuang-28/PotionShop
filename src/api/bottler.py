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
    with db.engine.begin() as connection:
        total_ml = [0, 0, 0, 0]
        for potion in potions_delivered:
            for idx in range(len(total_ml)):
                total_ml[idx] += potion.potion_type[idx] * potion.quantity
            recordExists = connection.execute(
                sqlalchemy.text(
                    f"SELECT 1 FROM potion_inventory \
                      WHERE potion_type = {potion.potion_type}"
                )
            )
            if recordExists.first():
                connection.execute(
                    sqlalchemy.text(
                        f"UPDATE potion_inventory \
                          SET quantity = quantity + {potion.quantity} \
                          WHERE potion_type = {potion.potion_type}"
                    )
                )
            else:
                connection.execute(
                    sqlalchemy.text(
                        f"INSERT INTO potion_inventory (quantity, potion_type) \
                          VALUES ({potion.quantity}, {potion.potion_type})"
                    )
                )
        connection.execute(
            sqlalchemy.text(
                f"UPDATE global_inventory \
                    SET num_red_ml = num_red_ml - {total_ml[0]}, \
                    num_green_ml = num_green_ml - {total_ml[1]}, \
                    num_blue_ml = num_blue_ml - {total_ml[2]}, \
                    num_dark_ml = num_dark_ml - {total_ml[3]}"
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
        inventory = (
            connection.execute(
                sqlalchemy.text(
                    "SELECT num_red_ml AS r, \
                            num_green_ml AS g, \
                            num_blue_ml AS b, \
                            num_dark_ml AS d \
                        FROM global_inventory"
                )
            )
        ).first()
    ml_in_barrels = (inventory.r, inventory.g, inventory.b, inventory.d)
    bottle_plan = []
    for idx in range(len(ml_in_barrels)):
        num_mixable_potions = int(ml_in_barrels[idx] / 100)
        if num_mixable_potions > 0:
            type = [0, 0, 0, 0]
            type[idx] = 100
            bottle_plan.append({"potion_type": type, "quantity": num_mixable_potions})
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
