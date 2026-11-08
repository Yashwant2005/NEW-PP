import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import config
from src.services.iv_engine import generate_ivs, get_random_nature, get_random_gender
from src.db.connection import get_db_connection

with open(config.DATA_DIR / "species.json") as f:
    ALL_SPECIES = json.load(f)

# Fallback species pool per region if detailed rdata is omitted
REGION_POOLS = {
    "kanto": ["caterpie", "weedle", "pidgey", "rattata", "spearow", "ekans", "pikachu", "sandshrew", "nidoran-f", "nidoran-m", "clefairy", "vulpix", "jigglypuff", "zubat", "oddish", "paras", "venonat", "diglett", "meowth", "psyduck", "mankey", "growlithe", "poliwag", "abra", "machop", "bellsprout", "tentacool", "geodude", "ponyta", "slowpoke", "magnemite", "farfetchd", "doduo", "seel", "grimer", "shellder", "gastly", "onix", "drowzee", "krabby", "voltorb", "exeggcute", "cubone", "hitmonlee", "hitmonchan", "lickitung", "koffing", "rhyhorn", "chansey", "tangela", "kangaskhan", "horsea", "goldeen", "staryu", "scyther", "jynx", "electabuzz", "magmar", "pinsir", "tauros", "magikarp", "lapras", "ditto", "eevee", "porygon", "omanyte", "kabuto", "aerodactyl", "snorlax", "articuno", "zapdos", "moltres", "dratini", "dragonair", "dragonite", "mewtwo", "mew"],
    "johto": ["sentret", "hoothoot", "ledyba", "spinarak", "chinchou", "pichu", "cleffa", "igglybuff", "togepi", "natu", "mareep", "marill", "sudowoodo", "aipom", "sunkern", "yanma", "wooper", "murkrow", "misdreavus", "unown", "wobbuffet", "girafarig", "pineco", "dunsparce", "gligar", "snubbull", "qwilfish", "shuckle", "heracross", "sneasel", "teddiursa", "slugma", "swinub", "corsola", "remoraid", "delibird", "mantine", "skarmory", "houndour", "phanpy", "stantler", "smeargle", "tyrogue", "miltank", "raikou", "entei", "suicune", "larvitar", "lugia", "ho-oh", "celebi"],
    "hoenn": ["poochyena", "zigzagoon", "wurmple", "lotad", "seedot", "taillow", "wingull", "ralts", "surskit", "shroomish", "slakoth", "nincada", "whismur", "makuhita", "azurill", "nosepass", "skitty", "sableye", "mawile", "aron", "meditite", "electrike", "plusle", "minun", "volbeat", "illumise", "roselia", "gulpin", "carvanha", "wailmer", "numel", "torkoal", "spoink", "spinda", "trapinch", "cacnea", "swablu", "zangoose", "seviper", "lunatone", "solrock", "barboach", "corphish", "baltoy", "lileep", "anorith", "feebas", "castform", "kecleon", "shuppet", "duskull", "tropius", "chimecho", "absol", "wynaut", "snorunt", "spheal", "relicanth", "luvdisc", "bagon", "beldum", "regirock", "regice", "registeel", "latias", "latios", "kyogre", "groudon", "rayquaza", "jirachi", "deoxys"]
}

async def generate_encounter(user_id: int, region: str = "kanto", is_safari: bool = False) -> Dict[str, Any]:
    pool = REGION_POOLS.get(region.lower(), REGION_POOLS["kanto"])

    # Rarity weight selection
    chosen_name = random.choice(pool)
    species_meta = ALL_SPECIES.get(chosen_name.lower(), {
        "id": 25,
        "name": chosen_name,
        "image": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
        "types": ["normal"],
        "catch_rate": 45
    })

    # Level generation (Wild: 5-30, Safari: 15-45)
    level = random.randint(15, 45) if is_safari else random.randint(5, 30)
    is_shiny = 1 if random.random() < (1.0 / 512.0 if is_safari else 1.0 / 2048.0) else 0

    ivs = generate_ivs()
    nature = get_random_nature()
    gender = get_random_gender()
    encounter_id = f"enc_{uuid.uuid4().hex[:12]}"
    expires_at = datetime.utcnow() + timedelta(minutes=2)

    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO encounters (
                encounter_id, user_id, species_id, species_name, level, is_shiny, is_safari,
                ivs, nature, gender, attempts_left, status, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 3, 'active', ?)
            """,
            (
                encounter_id, user_id, species_meta["id"], chosen_name.capitalize(),
                level, is_shiny, 1 if is_safari else 0, json.dumps(ivs), nature, gender, expires_at
            )
        )
        await conn.commit()
    finally:
        await conn.close()

    return {
        "encounter_id": encounter_id,
        "species_name": chosen_name.capitalize(),
        "species_id": species_meta["id"],
        "level": level,
        "is_shiny": bool(is_shiny),
        "is_safari": is_safari,
        "image": species_meta.get("image", ""),
        "types": species_meta.get("types", []),
        "catch_rate": species_meta.get("catch_rate", 45),
        "ivs": ivs,
        "nature": nature,
        "gender": gender
    }

async def get_active_encounter(encounter_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db_connection()
    try:
        async with conn.execute("SELECT * FROM encounters WHERE encounter_id = ? AND status = 'active'", (encounter_id,)) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["ivs"] = json.loads(d["ivs"])
                return d
            return None
    finally:
        await conn.close()
