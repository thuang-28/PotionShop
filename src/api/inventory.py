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
        audit = {
            "number_of_potions": inventory.total_potions,
            "ml_in_barrels": inventory.total_ml,
            "gold": inventory.gold,
        }
        print("[Log] Audit:", audit)
    return audit


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
                SELECT gold,
                       potion_capacity * 50 - (
                            SELECT COALESCE(SUM(quantity), 0) AS total_potions
                              FROM potion_inventory
                        ) AS num_craftable_pot,
                       potion_capacity * 10 AS potion_buy_threshold,
                       ml_capacity * 10000 - (num_red_ml + num_green_ml + num_blue_ml + num_dark_ml) AS num_containable_ml,
                       ml_capacity * 1000 AS ml_buy_threshold
                  FROM global_inventory
                """
            )
        ).first()
        gold = stats.gold
        if gold >= 1000 and stats.num_craftable_pot < stats.potion_buy_threshold:
            plan["potion_capacity"] = 1
            gold -= 1000
        if gold >= 1000 and stats.num_containable_ml < stats.ml_buy_threshold:
            plan["ml_capacity"] = 1
    print("[Log] Capacity purchase plan:", plan)
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
    print(f"[Log] Capacity delivered (ID {order_id}):", capacity_purchase)
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                """
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
    return "OK"
