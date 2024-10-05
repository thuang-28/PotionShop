import math

import sqlalchemy
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)


@router.get("/audit")
def get_inventory():
    """ """
    with db.engine.begin() as connection:
        inventory = connection.execute(
            sqlalchemy.text(
                "SELECT gold, \
                    num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_ml \
                FROM global_inventory"
            )
        ).first()
        potions = connection.execute(
            sqlalchemy.text(
                "SELECT SUM(quantity) AS total_potions \
                FROM potion_inventory"
            )
        ).first()
    return {
        "number_of_potions": potions.total_potions or 0,
        "ml_in_barrels": inventory.total_ml,
        "gold": inventory.gold,
    }


# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional
    capacity unit costs 1000 gold.
    """
    plan = {"potion_capacity": 0, "ml_capacity": 0}
    with db.engine.begin() as connection:
        stats = connection.execute(
            sqlalchemy.text(
                "SELECT num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_ml, \
                        gold, potion_capacity, ml_capacity FROM global_inventory"
            )
        ).first()
        total_bottles = (
            connection.execute(
                sqlalchemy.text("SELECT SUM(quantity) AS total FROM potion_inventory")
            )
            .first().total
            or 0
        )
    if stats.gold >= 1000:
        if (stats.potion_capacity - total_bottles) < 10:
            plan["ml_capacity"] = 1
        elif (stats.ml_capacity - stats.total_ml) < 500:
            plan["potion_capacity"] = 1
    return plan


class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int


# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase: CapacityPurchase, order_id: int):
    """
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional
    capacity unit costs 1000 gold.
    """
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                f"UPDATE global_inventory \
                  SET potion_capacity = potion_capacity + {capacity_purchase.potion_capacity}, \
                      ml_capacity = ml_capacity + {capacity_purchase.ml_capacity}"
            )
        )
    return "OK"
