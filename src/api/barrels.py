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
    """ """
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
    print(f"barrels delivered: {barrels_delivered} order_id: {order_id}")
    return "OK"


# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    with db.engine.begin() as connection:
        stats = (
            connection.execute(
                sqlalchemy.text(
                    """
                    SELECT gold,
                           ml_capacity,
                           num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_barrel_ml
                    FROM global_inventory
                    """
                )
            )
        ).first()
    purchase_plan = []
    total_price = 0
    total_ml = stats.total_barrel_ml
    while True:
        barrel = min(
            [
                item
                for item in wholesale_catalog
                if item.quantity > 0
                and stats.gold >= total_price + item.price
                and stats.ml_capacity * 10000 >= total_ml + item.ml_per_barrel
            ],
            key=lambda b: (
                (-1 / b.price) if b.potion_type[3] > 0 else b.price
            ),  # prioritize buying dark barrels over cheap barrels
            default=None,
        )
        if not barrel:
            break
        total_price += barrel.price
        total_ml += barrel.ml_per_barrel
        purchase_plan.append({"sku": barrel.sku, "quantity": 1})
        wholesale_catalog.remove(barrel)
    print(f"[Log] Purchase Plan: {purchase_plan}")
    return purchase_plan
