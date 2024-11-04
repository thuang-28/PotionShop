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
                        WHERE red = :red
                          AND green = :green
                          AND blue = :blue
                          AND dark = :dark
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
                    SELECT DISTINCT red_pct, green_pct, blue_pct, dark_pct,
                           SUM(qty_change) OVER (PARTITION BY potion_index.sku) AS quantity
                      FROM potion_index
                      JOIN potion_records ON potion_records.sku = potion_index.sku
                      JOIN potion_strategy ON potion_strategy.potion_sku = potion_records.sku
                       AND potion_strategy.day_of_week::text = TO_CHAR(now(), 'fmDay')
                     ORDER BY quantity;
                    """
                )
            )
        ).all()
        limits = (
            connection.execute(
                sqlalchemy.text(
                    """
                    WITH p AS (
                        SELECT
                            (SELECT SUM(potion_units) * 50 FROM capacity_records) -
                            (SELECT SUM(qty_change) FROM potion_records)
                        AS remaining
                    )
                    SELECT p.remaining AS potions_left,
                           COALESCE(SUM(red), 0) AS red_ml,
                           COALESCE(SUM(green), 0) AS green_ml,
                           COALESCE(SUM(blue), 0) AS blue_ml,
                           COALESCE(SUM(dark), 0) AS dark_ml
                      FROM ml_records, p
                     GROUP BY potions_left;
                    """
                )
            )
        ).one()
    bottle_plan = []
    ml_list = [limits.red_ml, limits.green_ml, limits.blue_ml, limits.dark_ml]
    potions_left = limits.potions_left
    for potion in todays_potions:
        potion_type = [potion.red_pct, potion.green_pct, potion.blue_pct, potion.dark_pct]
        max_qty = (
            min(ml_list[i] // potion_type[i] for i in range(4) if potion_type[i] != 0) // 2
        )
        num_mixable = min(max_qty, potions_left, 20)
        if num_mixable > 0:
            ml_list[0] -= num_mixable * potion.red_pct
            ml_list[1] -= num_mixable * potion.green_pct
            ml_list[2] -= num_mixable * potion.blue_pct
            ml_list[3] -= num_mixable * potion.dark_pct
            potions_left -= num_mixable
            bottle_plan.append(
                {
                    "potion_type": [
                        potion.red_pct,
                        potion.green_pct,
                        potion.blue_pct,
                        potion.dark_pct,
                    ],
                    "quantity": num_mixable,
                }
            )
    print("[Log] Bottle Plan:", bottle_plan)
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
