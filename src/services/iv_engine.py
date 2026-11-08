import random
from typing import Dict

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

def generate_ivs() -> Dict[str, int]:
    return {
        "hp": random.randint(0, 31),
        "atk": random.randint(0, 31),
        "def": random.randint(0, 31),
        "spa": random.randint(0, 31),
        "spd": random.randint(0, 31),
        "spe": random.randint(0, 31)
    }

def calculate_iv_percentage(ivs: Dict[str, int]) -> float:
    total = sum(ivs.values())
    return round((total / 186.0) * 100, 1)

def get_random_nature() -> str:
    return random.choice(NATURES)

def get_random_gender() -> str:
    return random.choice(["male", "female"])
