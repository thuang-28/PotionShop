import sqlalchemy
from fastapi import APIRouter, Depends
from pydantic import BaseModel

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
                    WITH ml AS (
                        SELECT 2500 * SUM(ml_units) AS threshold,
                               10000 * SUM(ml_units) AS limit
                          FROM capacity_records
                    )
                    SELECT (ml.limit - COALESCE(SUM(red + green + blue + dark), 0)) AS ml_left,
                           SUM(red) < ml.threshold AS needRed,
                           SUM(green) < ml.threshold AS needGreen,
                           SUM(blue) < ml.threshold AS needBlue,
                           SUM(dark) < ml.threshold AS needDark
                    FROM ml_records, ml
                    GROUP BY ml.limit, ml.threshold
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
    total_price = 0
    needML = (ml.needRed, ml.needGreen, ml.needBlue, ml.needDark)
    ml_left = ml.ml_left
    for i in range(4):
        if needML[i]:
            barrel = max(
                [
                    item
                    for item in wholesale_catalog
                    if item.potion_type[i] == 1
                    and gold >= total_price + item.price
                    and item.ml_per_barrel <= ml_left
                ],
                key=lambda b: b.ml_per_barrel,
                default=None,
            )
        total_price += barrel.price
        ml_left -= barrel.ml_per_barrel
        purchase_plan.append({"sku": barrel.sku, "quantity": 1})
    print("[Log] Purchase Plan:", purchase_plan)
    return purchase_plan
