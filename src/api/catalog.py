import sqlalchemy
from fastapi import APIRouter
from src import database as db
import re

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    with db.engine.begin() as connection:
        catalog = []
        potions = (
            connection.execute(
                sqlalchemy.text(
                    """
                    SELECT sku, quantity,
                           FLOOR(price * price_mult)::int4 AS mod_price,
                           red, green, blue, dark
                      FROM potion_inventory
                     WHERE quantity > 0
                     LIMIT 6
                    """
                )
            )
            .mappings()
            .fetchall()
        )
    for potion in potions:
        name = re.sub(r"([0-9]{1,3})([A-Z])_", r"\g<1>\g<2>, ", potion["sku"]).replace(
            ", POTION", " Potion"
        )
        catalog.append(
            {
                "sku": potion["sku"],
                "name": name,
                "quantity": potion["quantity"],
                "price": potion["mod_price"],
                "potion_type": [
                    potion["red"],
                    potion["green"],
                    potion["blue"],
                    potion["dark"],
                ],
            }
        )
    print("[Log] Available Catalog:", catalog)
    return catalog
