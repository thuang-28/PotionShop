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
                      WHERE red = {potion.potion_type[0]} \
                        AND green = {potion.potion_type[1]} \
                        AND blue = {potion.potion_type[2]} \
                        AND dark = {potion.potion_type[3]}"
                )
            ).first()
            if recordExists:
                connection.execute(
                    sqlalchemy.text(
                        f"UPDATE potion_inventory \
                          SET quantity = quantity + {potion.quantity} \
                          WHERE red = {potion.potion_type[0]} \
                            AND green = {potion.potion_type[1]} \
                            AND blue = {potion.potion_type[2]} \
                            AND dark = {potion.potion_type[3]}"
                    )
                )
            else:
                sku = ""
                colors = ("R", "G", "B", "D")
                for i in range(4):
                    if potion.potion_type[i] > 0:
                        sku += str(potion.potion_type[i]) + colors[i]
                sku += "_POTION"
                price = int(
                    potion.potion_type[0] * 0.55
                    + potion.potion_type[1] * 0.5
                    + potion.potion_type[2] * 0.65
                    + potion.potion_type[3] * 0.8
                )
                connection.execute(
                    sqlalchemy.text(
                        f"INSERT INTO potion_inventory (sku, quantity, price, \
                                                        red, green, blue, dark) \
                          VALUES ('{sku}', {potion.quantity}, {price}, \
                                   {potion.potion_type[0]}, {potion.potion_type[1]}, {potion.potion_type[2]}, {potion.potion_type[3]})"
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
                    "SELECT potion_capacity, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml \
                     FROM global_inventory"
                )
            )
        ).first()
        total_bottles = (
            connection.execute(
                sqlalchemy.text("SELECT SUM(quantity) AS total FROM potion_inventory")
            )
            .first()
            .total
            or 0
        )
    bottle_plan = []
    ml_tuple = inventory[1:]
    for idx in range(4):
        num_mixable_potions = min(
            int(ml_tuple[idx] / 100),
            inventory.potion_capacity * 50 - total_bottles,
        )
        total_bottles += num_mixable_potions
        if num_mixable_potions > 0:
            type = [0, 0, 0, 0]
            type[idx] = 100
            bottle_plan.append({"potion_type": type, "quantity": num_mixable_potions})
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
