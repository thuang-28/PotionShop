import sqlalchemy
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import numpy as np

from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)


class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int


@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """
    Posts delivery of barrels. order_id is a unique value representing
    a single delivery.
    """
    print(f"[Log] Barrels delivered (ID {order_id}):", barrels_delivered)
    total_ml = [
        sum(
            barrel.potion_type[i] * barrel.quantity * barrel.ml_per_barrel
            for barrel in barrels_delivered
        )
        for i in range(4)
    ]
    total_price = sum(barrel.price * barrel.quantity for barrel in barrels_delivered)

    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                """
                INSERT INTO ml_records (red, green, blue, dark)
                VALUES (:red, :green, :blue, :dark);
                INSERT INTO gold_records (change_in_gold)
                VALUES (:price * -1)
                """
            ),
            {
                "red": total_ml[0],
                "green": total_ml[1],
                "blue": total_ml[2],
                "dark": total_ml[3],
                "price": total_price,
            },
        )
    return "OK"


# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """
    Gets the plan for purchasing wholesale barrels. The call passes in a catalog of available barrels and the shop returns back which barrels they'd like to purchase and how many.
    """
    print("[Log] Barrel catalog:", wholesale_catalog)
    with db.engine.begin() as connection:
        ml = (
            connection.execute(
                sqlalchemy.text(
                    """
                    SELECT ARRAY[
                                SUM(red_pct * favorability),
                                SUM(green_pct * favorability),
                                SUM(blue_pct * favorability),
                                SUM(dark_pct * favorability)
                            ]
                      FROM potion_index
                      JOIN potion_strategy ON potion_strategy.potion_sku = potion_index.sku
                       AND potion_strategy.day_of_week::text = TO_CHAR(now(), 'fmDay')
                    """
                )
            )
        ).scalar_one()
        ml_left = connection.execute(
            sqlalchemy.text(
                """
                    SELECT
                        (SELECT 10000 * SUM(ml_units) FROM capacity_records)
                        - (SELECT COALESCE(SUM(red + green + blue + dark), 0) FROM ml_records)
                """
            )
        ).scalar_one()
        gold = (
            connection.execute(
                sqlalchemy.text("SELECT SUM(change_in_gold) FROM gold_records")
            )
        ).scalar_one()
    purchase_plan = []
    ranks = np.argsort(ml)[::-1]
    sorted_catalog = sorted(
        (
            b
            for b in wholesale_catalog
            if gold >= b.price and ml_left >= b.ml_per_barrel
        ),
        key=lambda b: b.ml_per_barrel,
        reverse=True,
    )  # sort catalog by ml, filter out unpurchaseable barrels
    ml_thres = int(ml_left // 4)
    for r in ranks:
        barrel = next(
            (
                b
                for b in sorted_catalog
                if b.potion_type[r] == 1
                and gold >= b.price
                and ml_left >= b.ml_per_barrel
            ),
            None,
        )
        if barrel:
            sorted_catalog.remove(barrel)
            qty = (
                int(
                    min(
                        min(ml_thres, ml_left) // barrel.ml_per_barrel,
                        gold // barrel.price,
                        barrel.quantity
                    )
                )
                if barrel.ml_per_barrel < ml_thres
                else 1
            )
            gold -= barrel.price * qty
            ml_left -= barrel.ml_per_barrel * qty
            purchase_plan.append({"sku": barrel.sku, "quantity": qty})
    print("[Log] Purchase Plan:", purchase_plan)
    return purchase_plan
