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
        for potion in potions_delivered:
            sku = ""
            colors = ("R", "G", "B", "D")
            for i in range(4):
                if potion.potion_type[i] > 0:
                    sku += str(potion.potion_type[i]) + colors[i]
            sku += "_POTION"
            base_price = int(
                potion.potion_type[0] * 0.5
                + potion.potion_type[1] * 0.5
                + potion.potion_type[2] * 0.5
                + potion.potion_type[3] * 0.75
            )
            connection.execute(
                sqlalchemy.text(
                    """
                    INSERT INTO potion_inventory (sku, quantity, price,
                                                  red, green, blue, dark)
                         VALUES (:sku, :quantity, :price,
                                 :red, :green, :blue, :dark)
                    ON CONFLICT (sku)
                      DO UPDATE
                            SET quantity = potion_inventory.quantity + :quantity
                    """
                ),
                {
                    "sku": sku,
                    "quantity": potion.quantity,
                    "price": base_price,
                    "red": potion.potion_type[0],
                    "green": potion.potion_type[1],
                    "blue": potion.potion_type[2],
                    "dark": potion.potion_type[3],
                },
            )
        total_ml = [
            sum(potion.potion_type[i] * potion.quantity for potion in potions_delivered)
            for i in range(4)
        ]
        connection.execute(
            sqlalchemy.text(
                """
                UPDATE global_inventory
                   SET num_red_ml = num_red_ml - :r,
                       num_green_ml = num_green_ml - :g,
                       num_blue_ml = num_blue_ml - :b,
                       num_dark_ml = num_dark_ml - :d
                """
            ),
            {"r": total_ml[0], "g": total_ml[1], "b": total_ml[2], "d": total_ml[3]},
        )
    print(f"[Log] Potions delivered: {potions_delivered} Order Id: {order_id}")
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
                    """
                    SELECT num_red_ml, num_green_ml, num_blue_ml, num_dark_ml,
                           potion_capacity,
                           (
                               SELECT COALESCE(SUM(quantity), 0) AS total_potions
                                 FROM potion_inventory
                            )
                    FROM global_inventory
                    """
                )
            )
        ).first()
    bottle_plan = []
    ml_list = list(inventory[0:4])
    total_bottles = inventory.total_potions
    num_mixable = [0, 0, 0, 0]
    for idx in range(4):
        num_pure_potions = min(
            int(ml_list[idx] / 200), inventory.potion_capacity * 50 - total_bottles
        )
        if num_pure_potions > 0:
            total_bottles += num_pure_potions
            ml_list[idx] = ml_list[idx] - (num_pure_potions * 100)
            type = [0, 0, 0, 0]
            type[idx] = 100
            bottle_plan.append({"potion_type": type, "quantity": num_pure_potions})
        num_mixable[idx] = int(ml_list[idx] / 150)
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]:
        if ml_list[i] >= 50 and ml_list[j] >= 50:
            num_mixed_potions = min(
                num_mixable[i],
                num_mixable[j],
                inventory.potion_capacity * 50 - total_bottles,
            )
            if num_mixed_potions > 0:
                total_bottles += num_mixed_potions
                ml_list[i] = ml_list[i] - (num_mixed_potions * 50)
                ml_list[j] = ml_list[j] - (num_mixed_potions * 50)
                type = [0, 0, 0, 0]
                type[i] = 50
                type[j] = 50
                bottle_plan.append({"potion_type": type, "quantity": num_mixed_potions})
    print(f"[Log] Bottle Plan: {bottle_plan}")
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
