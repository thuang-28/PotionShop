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
                """
                SELECT gold,
                       (
                           SELECT COALESCE(SUM(quantity), 0) AS total_potions
                             FROM potion_inventory
                        ),
                       num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_ml
                  FROM global_inventory
                """
            )
        ).first()
    return {
        "number_of_potions": inventory.total_potions,
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
                """
                SELECT num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_ml,
                       (
                            SELECT COALESCE(SUM(quantity), 0) AS total_potions
                              FROM potion_inventory
                        ),
                       gold, potion_capacity, ml_capacity
                  FROM global_inventory
                """
            )
        ).first()
    if stats.gold >= 1000:
        if (stats.potion_capacity * 50 - stats.total_potions) < 10:
            plan["potion_capacity"] = 1
        elif (stats.ml_capacity * 10000 - stats.total_ml) < 500:
            plan["ml_capacity"] = 1
    print(f"[Log] Capacity purchase plan: {plan}")
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
                f"""
                UPDATE global_inventory
                   SET potion_capacity = potion_capacity + :new_pot_units,
                       ml_capacity = ml_capacity + :new_ml_units,
                       gold = gold - ((:new_pot_units + :new_ml_units) * 1000)
                """
            ),
            {
                "new_pot_units": capacity_purchase.potion_capacity,
                "new_ml_units": capacity_purchase.ml_capacity,
            },
        )
        print(
            f"[Log] Capacity delivered: Potion {capacity_purchase.potion_capacity}, ML {capacity_purchase.ml_capacity}, order id: {order_id}"
        )
    return "OK"
