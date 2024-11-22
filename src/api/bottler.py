import sqlalchemy
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)


class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int


@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """Posts delivery of potions. order_id is a unique value representing a single delivery."""
    print(f"[Log] Potions delivered: {potions_delivered} Order id: {order_id}")
    with db.engine.begin() as connection:
        total_ml = [0, 0, 0, 0]
        for potion in potions_delivered:
            for i in range(4):
                total_ml[i] += potion.potion_type[i] * potion.quantity
            connection.execute(
                sqlalchemy.text(
                    """
                    INSERT INTO potion_records (sku, qty_change)
                    SELECT sku, :quantity FROM potion_index
                        WHERE red_pct = :red
                          AND green_pct = :green
                          AND blue_pct = :blue
                          AND dark_pct = :dark
                    """
                ),
                {
                    "quantity": potion.quantity,
                    "red": potion.potion_type[0],
                    "green": potion.potion_type[1],
                    "blue": potion.potion_type[2],
                    "dark": potion.potion_type[3],
                },
            )
        connection.execute(
            sqlalchemy.text(
                """
                INSERT INTO ml_records (red, green, blue, dark)
                     VALUES (:red * -1, :green * -1, :blue * -1, :dark * -1)
                """
            ),
            {
                "red": total_ml[0],
                "green": total_ml[1],
                "blue": total_ml[2],
                "dark": total_ml[3],
            },
        )
    return "OK"


@router.post("/plan")
def get_bottle_plan():
    """Gets the plan for bottling potions from barrels."""

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    with db.engine.begin() as connection:
        todays_potions = (
            connection.execute(
                sqlalchemy.text(
                    """
                    WITH TodayPotions AS (
                        SELECT potion_index.sku AS potion,
                               ARRAY[red_pct, green_pct, blue_pct, dark_pct] AS potion_type,
                               COALESCE(favorability, 1.0) AS favorability
                          FROM potion_index
                     LEFT JOIN potion_strategy ON potion_strategy.potion_sku = potion_index.sku
                           AND potion_strategy.day_of_week::text = TO_CHAR(now(), 'fmDay')
                           AND COALESCE(favorability, 1.0) > 0
                           AND do_bottle = TRUE
                    ),
                    RecentAmtSold AS (
                        SELECT potion, COALESCE(SUM(quantity), 0) AS recent_amt_sold
                          FROM TodayPotions
                     LEFT JOIN cart_items ON cart_items.sku = potion
                           AND item_id IN (SELECT item_id FROM cart_items
                                           ORDER BY item_id DESC LIMIT 50)
                      GROUP BY potion
                    ),
                    magic (pt_limit) AS (
                        SELECT per_bottle_limit
                        FROM magic_numbers
                        LIMIT 1
                    )
                    SELECT DISTINCT potion_type, recent_amt_sold, favorability,
                                    magic.pt_limit - COALESCE(SUM(qty_change), 0) AS brewable_pt
                               FROM TodayPotions CROSS JOIN magic
                               JOIN RecentAmtSold ON RecentAmtSold.potion = TodayPotions.potion
                          LEFT JOIN potion_records ON potion_records.sku = TodayPotions.potion
                           GROUP BY potion_type, favorability, recent_amt_sold, pt_limit
                             HAVING magic.pt_limit > COALESCE(SUM(qty_change), 0) 
                           ORDER BY recent_amt_sold DESC, favorability DESC, brewable_pt DESC
                    """
                )
            )
        ).all()
        limits = (
            connection.execute(
                sqlalchemy.text(
                    """
                    WITH ml (list) AS (
                        SELECT 
                            ARRAY[
                               COALESCE(SUM(red), 0),
                               COALESCE(SUM(green), 0),
                               COALESCE(SUM(blue), 0),
                               COALESCE(SUM(dark), 0)
                            ]
                        FROM ml_records
                    )
                    SELECT (SELECT SUM(potion_units) * 50 FROM capacity_records) -
                                (SELECT COALESCE(SUM(qty_change), 0) FROM potion_records) AS potions_left,
                            ml.list AS ml_list
                      FROM ml
                    """
                )
            )
        ).one()
    ml_list = limits.ml_list
    potions_left = limits.potions_left
    bottle_plan = []
    for potion in todays_potions:
        qty = int(
            min(
                min(
                    ml_list[i] // potion.potion_type[i]
                    for i in range(4)
                    if potion.potion_type[i] > 0
                ),
                potions_left,
                potion.brewable_pt
            )
        )
        if qty > 0:
            for i in range(4):
                ml_list[i] -= qty * potion.potion_type[i]
            potions_left -= qty
            bottle_plan.append(
                {
                    "potion_type": potion.potion_type,
                    "quantity": qty,
                }
            )
    print("[Log] Bottle Plan:", bottle_plan)
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
