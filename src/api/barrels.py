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
                f"UPDATE global_inventory \
                    SET num_red_ml = num_red_ml + {total_ml[0]}, \
                    num_green_ml = num_green_ml + {total_ml[1]}, \
                    num_blue_ml = num_blue_ml + {total_ml[2]}, \
                    num_dark_ml = num_dark_ml + {total_ml[3]}, \
                    gold = gold - {total_price}"
            )
        )
    print(f"barrels delivered: {barrels_delivered} order_id: {order_id}")
    return "OK"


# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    # Barrel(sku='MINI_RED_BARREL', ml_per_barrel=200, potion_type=[1, 0, 0, 0], price=60, quantity=1)
    # Barrel(sku='SMALL_RED_BARREL', ml_per_barrel=500, potion_type=[1, 0, 0, 0], price=100, quantity=10)
    # Barrel(sku='LARGE_RED_BARREL', ml_per_barrel=10000, potion_type=[1, 0, 0, 0], price=500, quantity=30)

    # Barrel(sku='MINI_GREEN_BARREL', ml_per_barrel=200, potion_type=[0, 1, 0, 0], price=60, quantity=1)
    # Barrel(sku='SMALL_GREEN_BARREL', ml_per_barrel=500, potion_type=[0, 1, 0, 0], price=100, quantity=10)
    # Barrel(sku='LARGE_GREEN_BARREL', ml_per_barrel=10000, potion_type=[0, 1, 0, 0], price=400, quantity=30)

    # Barrel(sku='MINI_BLUE_BARREL', ml_per_barrel=200, potion_type=[0, 0, 1, 0], price=60, quantity=1)
    # Barrel(sku='SMALL_BLUE_BARREL', ml_per_barrel=500, potion_type=[0, 0, 1, 0], price=120, quantity=10)
    # Barrel(sku='LARGE_BLUE_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 1, 0], price=600, quantity=30)

    # Barrel(sku='LARGE_DARK_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 0, 1], price=750, quantity=10)

    with db.engine.begin() as connection:
        stats = (
            connection.execute(
                sqlalchemy.text(
                    "SELECT gold, ml_capacity, \
                            num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_barrel_ml \
                     FROM global_inventory"
                )
            )
        ).first()
        total_inventory_ml = connection.execute(
            sqlalchemy.text(
                "SELECT SUM(r), SUM(g), SUM(b), SUM(d) \
                 FROM ( \
                    SELECT num_red_ml AS r, \
                        num_green_ml AS g, \
                        num_blue_ml AS b, \
                        num_dark_ml AS d \
                    FROM global_inventory UNION ALL \
                        SELECT red * quantity AS r, \
                            green * quantity AS g, \
                            blue * quantity AS b, \
                            dark * quantity AS d \
                    FROM potion_inventory WHERE quantity > 0 \
                ) AS mls"
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
    print(f"Purchase Plan: {purchase_plan}")
    return purchase_plan
