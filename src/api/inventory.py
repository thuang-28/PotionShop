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
    with db.engine.begin() as connection:
        stats = connection.execute(
            sqlalchemy.text(
                """
                SELECT (SELECT SUM(change_in_gold) FROM gold_records) AS gold,
                       GREATEST(5 - SUM(potion_units), 1) AS pt_buy_qty,
                       GREATEST(5 - SUM(ml_units), 1) AS ml_buy_qty
                  FROM capacity_records
                """
            )
        ).one()
        gold = stats.gold
        plan = {}
        pt_qty = int(min(stats.pt_buy_qty, gold // 1000))
        gold -= pt_qty * 1000
        plan["potion_capacity"] = pt_qty
        ml_qty = int(min(stats.ml_buy_qty, gold // 1000))
        plan["ml_capacity"] = ml_qty
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
