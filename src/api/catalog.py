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
                    SELECT potion_index.sku, price,
                           SUM(qty_change) AS quantity,
                           red_pct, green_pct, blue_pct, dark_pct
                      FROM potion_index JOIN potion_records
                        ON potion_index.sku = potion_records.sku 
                     GROUP BY potion_index.sku
                    HAVING SUM(qty_change) > 0
                     ORDER BY quantity DESC
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
                "potion_type": [
                    potion.red_pct,
                    potion.green_pct,
                    potion.blue_pct,
                    potion.dark_pct,
                ],
            }
        )
    print("[Log] Available Catalog:", catalog)
    return catalog
