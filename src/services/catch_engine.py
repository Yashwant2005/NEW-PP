import random
import math
from typing import Dict, Any, Tuple
from src.db.connection import get_db_connection

BALL_MULTIPLIERS = {
    "regular": 1.0,
    "great": 1.5,
    "ultra": 2.5,
    "safari": 3.0,
    "master": 255.0
}

async def attempt_catch(user_id: int, encounter: Dict[str, Any], ball_type: str) -> Tuple[bool, str]:
    conn = await get_db_connection()
    try:
        # Check and deduct ball
        async with conn.execute(
            "SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = ?",
            (user_id, ball_type)
        ) as cur:
            row = await cur.fetchone()
            if not row or row["quantity"] <= 0:
                return False, f"⚠️ You don't have any {ball_type.capitalize()} Balls left!"

        # Deduct ball atomically
        await conn.execute(
            "UPDATE user_inventory SET quantity = quantity - 1 WHERE user_id = ? AND item_id = ?",
            (user_id, ball_type)
        )

        # Calculate catch probability
        ball_mult = BALL_MULTIPLIERS.get(ball_type.lower(), 1.0)
        catch_rate = encounter.get("catch_rate", 45)
        level = encounter.get("level", 10)

        # Modified Gen 3/4 catch chance
        # max_chance = ( (3 * max_hp - 2 * hp) * (catch_rate * ball_mult) ) / (3 * max_hp)
        base_factor = (catch_rate * ball_mult) / (3.0 * (1 + level / 50.0))
        probability = min(0.98, max(0.10, base_factor / 100.0))

        if ball_type.lower() == "master":
            probability = 1.0

        success = random.random() < probability

        if success:
            # Mark encounter caught
            await conn.execute(
                "UPDATE encounters SET status = 'caught' WHERE encounter_id = ?",
                (encounter["encounter_id"],)
            )
            # Add Pokemon to user_pokemon
            ivs = encounter["ivs"]
            await conn.execute(
                """
                INSERT INTO user_pokemon (
                    user_id, species_id, species_name, nickname, level, exp, gender, nature, ability,
                    is_shiny, iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'default', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, encounter["species_id"], encounter["species_name"], encounter["species_name"],
                    encounter["level"], encounter["gender"], encounter["nature"],
                    1 if encounter.get("is_shiny") else 0,
                    ivs["hp"], ivs["atk"], ivs["def"], ivs["spa"], ivs["spd"], ivs["spe"]
                )
            )

            # Grant catch reward (coins)
            coins_reward = random.randint(25, 100) * (2 if encounter.get("is_shiny") else 1)
            await conn.execute(
                "UPDATE users SET coins = coins + ? WHERE telegram_id = ?",
                (coins_reward, user_id)
            )
            await conn.commit()
            return True, f"Gotcha! <b>{encounter['species_name']}</b> was caught! 🌟 (+{coins_reward} PokéCoins)"
        else:
            # Check attempts left
            attempts_left = encounter["attempts_left"] - 1
            if attempts_left <= 0 or (encounter.get("is_safari") and random.random() < 0.40):
                await conn.execute(
                    "UPDATE encounters SET status = 'fled', attempts_left = 0 WHERE encounter_id = ?",
                    (encounter["encounter_id"],)
                )
                await conn.commit()
                return False, f"💨 Oh no! The wild <b>{encounter['species_name']}</b> fled!"
            else:
                await conn.execute(
                    "UPDATE encounters SET attempts_left = ? WHERE encounter_id = ?",
                    (attempts_left, encounter["encounter_id"])
                )
                await conn.commit()
                return False, f"Argh! Almost had it! ({attempts_left} attempts remaining)"
    finally:
        await conn.close()
