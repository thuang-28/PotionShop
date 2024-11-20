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
                    WITH cap (ml) AS (SELECT 10000 * SUM(ml_units) FROM capacity_records)
                    SELECT cap.ml - COALESCE(SUM(red + green + blue + dark), 0) AS remaining,
                           FLOOR((cap.ml * 0.85) / 3)::bigint AS thres,
                           ARRAY[
                               COALESCE(SUM(red), 0),
                               COALESCE(SUM(green), 0),
                               COALESCE(SUM(blue), 0),
                               COALESCE(SUM(dark), 0)
                           ] AS list
                      FROM ml_records, cap
                      GROUP BY cap.ml
                    """
                )
            )
        ).one()
        gold = (
            connection.execute(
                sqlalchemy.text("SELECT SUM(change_in_gold) FROM gold_records")
            )
        ).scalar_one()
    purchase_plan = []
    ml_left = ml.remaining
    ranks = np.argsort(ml.list)
    sorted_catalog = sorted(
        (
            b
            for b in wholesale_catalog
            if gold >= b.price and ml_left >= b.ml_per_barrel
        ),
        key=lambda b: b.ml_per_barrel,
        reverse=True,
    )  # sort catalog by ml, filter out unpurchaseable barrels
    for r in ranks:
        if ml.list[r] < ml.thres:
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
                diff = ml.thres - ml.list[r]
                sorted_catalog.remove(barrel)
                qty = int(
                    max(
                        min(
                            min(diff, ml_left) // barrel.ml_per_barrel,
                            gold // barrel.price,
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
