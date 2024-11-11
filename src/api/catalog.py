import sqlalchemy
from fastapi import APIRouter
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Retrieves the catalog of items. Each unique item combination should have only a single price. You can have at most 6 potion SKUs offered in your catalog at one time.
    """
    with db.engine.begin() as connection:
        potions = connection.execute(
            sqlalchemy.text(
                """
                      WITH st AS (
                           SELECT potion_sku, favorability
                             FROM potion_strategy
                            WHERE potion_strategy.day_of_week::text = TO_CHAR(now(), 'fmDay')
                          )
                    SELECT potion_index.sku, price,
                           SUM(qty_change) AS quantity,
                           ARRAY[red_pct, green_pct, blue_pct, dark_pct] AS type
                      FROM potion_index
                      JOIN potion_records ON potion_index.sku = potion_records.sku
                 LEFT JOIN st ON potion_index.sku = st.potion_sku
                     GROUP BY potion_index.sku, st.favorability
                    HAVING SUM(qty_change) > 0
                     ORDER BY COALESCE(st.favorability, 1.0) DESC,
                              quantity DESC
                     LIMIT 6
                    """
            )
        ).all()
    catalog = []
    for potion in potions:
        name = potion.sku.replace("_", " ").title()
        catalog.append(
            {
                "sku": potion.sku,
                "name": name,
                "quantity": potion.quantity,
                "price": potion.price,
                "potion_type": potion.type,
            }
        )
    print("[Log] Available Catalog:", catalog)
    return catalog
