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
    """
    Return a summary of your current number of potions, ml, and gold.
    """
    with db.engine.begin() as connection:
        inventory = connection.execute(
            sqlalchemy.text(
                """
                SELECT (SELECT COALESCE(SUM(qty_change), 0) FROM potion_records) AS total_potions,
                       (SELECT COALESCE(SUM(red + green + blue + dark), 0) FROM ml_records) AS total_ml,
                       (SELECT SUM(change_in_gold) FROM gold_records) AS gold
                """
            )
        ).one()
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
                WITH capacity (p, ml) AS (
                    SELECT SUM(potion_units), SUM(ml_units)
                      FROM capacity_records
                ),
                potions (total) AS (
                    SELECT COALESCE(SUM(qty_change), 0)
                      FROM potion_records
                ),
                ml (total) AS (
                    SELECT COALESCE(SUM(red + green + blue + dark), 0)
                      FROM ml_records
                )
                SELECT (SELECT SUM(change_in_gold) FROM gold_records) AS gold,
                       capacity.p * 50 - potions.total AS num_craftable_pot,
                       capacity.p * 15 AS potion_buy_threshold,
                       capacity.ml * 10000 - ml.total AS num_containable_ml,
                       capacity.ml * 1500 AS ml_buy_threshold
                  FROM capacity, potions, ml
                """
            )
        ).one()
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
                INSERT INTO capacity_records (potion_units, ml_units)
                     VALUES (:new_pot_units, :new_ml_units);
                INSERT INTO gold_records (change_in_gold)
                     VALUES ((:new_pot_units + :new_ml_units) * -1000)
                """
            ),
            {
                "new_pot_units": capacity_purchase.potion_capacity,
                "new_ml_units": capacity_purchase.ml_capacity,
            },
        )
    return "OK"
