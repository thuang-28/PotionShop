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
                    "SELECT sku, quantity, red, green, blue, dark \
                     FROM potion_inventory \
                     WHERE quantity > 0 \
                     LIMIT 6"
                )
            )
            .mappings()
            .fetchall()
        )
    for potion in potions:
        name = re.sub(r"([0-9]{1,3})([A-Z])_", r"$1% $2, ", potion["sku"]).replace(
            ", POTION", " Potion"
        )
        price = int(
            potion["red"] * 0.6
            + potion["green"] * 0.5
            + potion["blue"] * 0.7
            + potion["dark"] * 0.85
        )
        catalog.append(
            {
                "sku": potion["sku"],
                "name": name,
                "quantity": potion["quantity"],
                "price": price,
                "potion_type": [
                    potion["red"],
                    potion["green"],
                    potion["blue"],
                    potion["dark"],
                ],
            }
        )
    return catalog
