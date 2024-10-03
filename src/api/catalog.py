import sqlalchemy
from fastapi import APIRouter
from src import database as db

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
                    "SELECT quantity, potion_type \
                                 FROM global_potions \
                                 WHERE quantity > 0"
                )
            )
            .mappings()
            .fetchall()
        )
    for potion in potions:
        # modify implementation using SKU table later
        match potion["potion_type"]:
            case [100, 0, 0, 0]:
                name = "Red Potion"
                price = 50
            case [0, 100, 0, 0]:
                name = "Green Potion"
                price = 50
            case [0, 0, 100, 0]:
                name = "Blue Potion"
                price = 50
            case _:
                colors = ("Red", "Green", "Blue", "Dark")
                percentages = []
                for idx in range(len(potion["potion_type"])):
                    percent = potion["potion_type"][idx]
                    if percent > 0:
                        percentages.append(percent + "% " + colors[idx])
                name = " ".join(percentages) + " Potion"
        catalog.append(
            {
                "sku": name.upper().replace("%", "_").replace(" ", "_"),
                "name": name,
                "quantity": potion["quantity"],
                "price": price,
                "potion_type": potion["potion_type"],
            }
        )
    return catalog
