import json
from typing import Optional, Dict, Any
from src.db.connection import get_db_connection
import config

async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        async with conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    finally:
        await conn.close()

async def create_user(telegram_id: int, username: Optional[str], first_name: Optional[str], region: str = "kanto") -> Dict[str, Any]:
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, selected_region, coins, league_points, safari_passes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                updated_at=CURRENT_TIMESTAMP
            """,
            (telegram_id, username, first_name, region, config.DEFAULT_COINS, 0, config.DEFAULT_SAFARI_PASSES)
        )

        # Give initial starter inventory
        for ball, qty in config.DEFAULT_BALLS.items():
            await conn.execute(
                """
                INSERT INTO user_inventory (user_id, item_id, item_type, quantity)
                VALUES (?, ?, 'ball', ?)
                ON CONFLICT(user_id, item_id) DO NOTHING
                """,
                (telegram_id, ball, qty)
            )

        await conn.commit()
    finally:
        await conn.close()

    return await get_user(telegram_id)

async def give_starter_pokemon(user_id: int, species_name: str) -> Dict[str, Any]:
    from src.services.iv_engine import generate_ivs, get_random_nature, get_random_gender
    species_name = species_name.lower()
    species_id_map = {"bulbasaur": 1, "charmander": 4, "squirtle": 7, "pikachu": 25, "chikorita": 152, "cyndaquil": 155, "totodile": 158}
    species_id = species_id_map.get(species_name, 25)

    ivs = generate_ivs()
    nature = get_random_nature()
    gender = get_random_gender()

    conn = await get_db_connection()
    try:
        cur = await conn.execute(
            """
            INSERT INTO user_pokemon (
                user_id, species_id, species_name, nickname, level, exp, gender, nature, ability,
                iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, species_id, species_name.capitalize(), species_name.capitalize(), 5, 0, gender, nature, "overgrow" if "bulb" in species_name else ("blaze" if "char" in species_name else "torrent"),
                ivs["hp"], ivs["atk"], ivs["def"], ivs["spa"], ivs["spd"], ivs["spe"]
            )
        )
        poke_id = cur.lastrowid
        await conn.commit()
        return {"id": poke_id, "species": species_name, "level": 5, "ivs": ivs}
    finally:
        await conn.close()
