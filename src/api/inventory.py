import math

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
    """ """
    with db.engine.begin() as connection:
        inventory = connection.execute(
            sqlalchemy.text(
                "SELECT gold, \
                    num_red_ml + num_green_ml + num_blue_ml + num_dark_ml AS total_ml \
                FROM global_inventory"
            )
        ).first()
        potions = connection.execute(
            sqlalchemy.text(
                "SELECT SUM(quantity) AS total_potions \
                FROM global_potions"
            )
        ).first()
    return {
        "number_of_potions": potions.total_potions if potions.total_potions else 0,
        "ml_in_barrels": inventory.total_ml,
        "gold": inventory.gold,
    }


# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional
    capacity unit costs 1000 gold.
    """

    return {"potion_capacity": 0, "ml_capacity": 0}


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

    return "OK"
