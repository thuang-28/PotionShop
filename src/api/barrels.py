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
    total_ml = [0, 0, 0, 0]
    total_price = 0
    for barrel in barrels_delivered:
        color_idx = barrel.potion_type.index(1)
        total_ml[color_idx] += barrel.ml_per_barrel * barrel.quantity
        total_price += barrel.price * barrel.quantity

    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                f"""
                UPDATE global_inventory
                   SET num_red_ml = num_red_ml + {total_ml[0]},
                       num_green_ml = num_green_ml + {total_ml[1]},
                       num_blue_ml = num_blue_ml + {total_ml[2]},
                       num_dark_ml = num_dark_ml + {total_ml[3]},
                       gold = gold - {total_price}
                """
            )
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
        total_inventory_ml = connection.execute(
            sqlalchemy.text(
                """
                SELECT SUM(num_red_ml) +
                         (
                             SELECT COALESCE(SUM(red * quantity), 0)
                               FROM potion_inventory
                         ) AS r,
                       SUM(num_green_ml) +
                         (
                             SELECT COALESCE(SUM(green * quantity), 0)
                               FROM potion_inventory
                         ) AS g,
                       SUM(num_blue_ml) +
                         (
                             SELECT COALESCE(SUM(blue * quantity), 0)
                               FROM potion_inventory
                         ) AS b,
                       SUM(num_dark_ml) +
                         (
                             SELECT COALESCE(SUM(dark * quantity), 0)
                               FROM potion_inventory
                         ) AS d
                FROM global_inventory
                """
            )
        ).first()
    purchase_plan = []
    priority_idx = total_inventory_ml.index(min(total_inventory_ml))
    barrel = max(
        [
            item
            for item in wholesale_catalog
            if item.potion_type[priority_idx] == 1
            and stats.gold >= item.price
            and stats.ml_capacity * 10000 >= stats.total_barrel_ml + item.ml_per_barrel
        ],
        key=lambda b: b.ml_per_barrel,
        default=None,
    )
    if barrel:
        purchase_plan.append({"sku": barrel.sku, "quantity": 1})
    print(f"[Log] Purchase Plan: {purchase_plan}")
    return purchase_plan
