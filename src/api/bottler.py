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
                    SELECT ARRAY[red_pct, green_pct, blue_pct, dark_pct] AS potion_type,
                           COALESCE(SUM(qty_change), 0) AS quantity
                      FROM potion_index
                      LEFT JOIN potion_records ON potion_records.sku = potion_index.sku
                      JOIN potion_strategy ON potion_strategy.potion_sku = potion_index.sku
                       AND potion_strategy.day_of_week::text = TO_CHAR(now(), 'fmDay')
                     GROUP BY potion_index.sku
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
                           ARRAY[
                               COALESCE(SUM(red), 0),
                               COALESCE(SUM(green), 0),
                               COALESCE(SUM(blue), 0),
                               COALESCE(SUM(dark), 0)
                            ] AS ml_list
                      FROM ml_records, p
                     GROUP BY potions_left;
                    """
                )
            )
        ).one()
    bottle_plan = []
    ml_list = limits.ml_list
    potions_left = limits.potions_left
    for potion in todays_potions:
        max_qty = (
            min(ml_list[i] // potion.potion_type[i] for i in range(4) if potion.potion_type[i] != 0) // 2
        )
        num_mixable = min(max_qty, potions_left, 20)
        if num_mixable > 0:
            for i in range(4):
                ml_list[i] -= num_mixable * potion.potion_type[i]
            potions_left -= num_mixable
            bottle_plan.append(
                {
                    "potion_type": potion.potion_type,
                    "quantity": num_mixable,
                }
            )
    print("[Log] Bottle Plan:", bottle_plan)
    return bottle_plan


if __name__ == "__main__":
    print(get_bottle_plan())
