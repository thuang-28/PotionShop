import sqlalchemy
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src import database as db
from src.api import auth

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)


@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                """
                DELETE FROM gold_records;
                INSERT INTO gold_records DEFAULT VALUES;
                DELETE FROM capacity_records;
                INSERT INTO capacity_records DEFAULT VALUES;
                DELETE FROM potion_records;
                DELETE FROM ml_records;
                """
            )
        )
    print("[Log] Game state has been reset.")
    return "OK"
