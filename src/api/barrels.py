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
        res = connection.execute(
            sqlalchemy.text(
                """
                WITH magic (budget, ml_limit) AS (
                    SELECT per_barrel_budget, per_barrel_ml_limit
                      FROM magic_numbers
                     LIMIT 1
                )
                SELECT (SELECT SUM(change_in_gold) FROM gold_records) AS gold,
                       (SELECT SUM(ml_units) * 10000 FROM capacity_records) -
                            COALESCE(SUM(red + green + blue + dark), 0) AS ml_left,
                       magic.budget,
                       ARRAY[
                            magic.ml_limit - COALESCE(SUM(red), 0),
                            magic.ml_limit - COALESCE(SUM(green), 0),
                            magic.ml_limit - COALESCE(SUM(blue), 0),
                            magic.ml_limit - COALESCE(SUM(dark), 0)
                        ] AS buyable_ml
                  FROM ml_records CROSS JOIN magic
                 GROUP BY budget, ml_limit
                """
            )
        ).one()
    gold = res.gold
    ml_left = res.ml_left
    ranks = np.argsort(res.buyable_ml)[::-1]
    sorted_catalog = sorted((b for b in wholesale_catalog), key=lambda b: b.ml_per_barrel, reverse=True)  # sort catalog by ml
    purchase_plan = []
    for r in ranks:
        if res.buyable_ml[r] > 0:
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
                qty = int(
                    max(
                        min(
                            min(res.buyable_ml[r], ml_left) // barrel.ml_per_barrel,
                            min(res.budget, gold) // barrel.price,
                            barrel.quantity,
                        ),
                        1
                    ),
                )
                gold -= barrel.price * qty
                ml_left -= barrel.ml_per_barrel * qty
                purchase_plan.append({"sku": barrel.sku, "quantity": qty})
    print("[Log] Purchase Plan:", purchase_plan)
    return purchase_plan
