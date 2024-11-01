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
                UPDATE global_inventory
                   SET num_red_ml = num_red_ml + :new_red,
                       num_green_ml = num_green_ml + :new_green,
                       num_blue_ml = num_blue_ml + :new_blue,
                       num_dark_ml = num_dark_ml + :new_dark,
                       gold = gold - :total_price
                """
            ),
            {
                "new_red": total_ml[0],
                "new_green": total_ml[1],
                "new_blue": total_ml[2],
                "new_dark": total_ml[3],
                "total_price": total_price,
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
        stats = (
            connection.execute(
                sqlalchemy.text(
                    """
                    SELECT gold,
                           (ml_capacity * 10000 - (num_red_ml + num_green_ml + num_blue_ml + num_dark_ml)) AS ml_left,
                           num_red_ml < 2500 AS needRed,
                           num_green_ml < 2500 AS needGreen,
                           num_blue_ml < 2500 AS needBlue,
                           num_dark_ml < 2500 AS needDark
                    FROM global_inventory
                    """
                )
            )
        ).one()
    purchase_plan = []
    total_price = 0
    needML = (stats.needRed, stats.needGreen, stats.needBlue, stats.needDark)
    ml_left = stats.ml_left
    for i in range(4):
        if needML[i]:
            barrel = max(
                [
                    item
                    for item in wholesale_catalog
                    if item.potion_type[i] == 1
                    and stats.gold >= total_price + item.price
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
