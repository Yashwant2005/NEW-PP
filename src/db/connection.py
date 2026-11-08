import sqlite3
import aiosqlite
from typing import AsyncGenerator
import config

INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=15000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    selected_region TEXT DEFAULT 'kanto',
    coins INTEGER DEFAULT 1000,
    league_points INTEGER DEFAULT 0,
    safari_passes INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_pokemon (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL,
    species_name TEXT NOT NULL,
    nickname TEXT,
    level INTEGER DEFAULT 5,
    exp INTEGER DEFAULT 0,
    gender TEXT,
    nature TEXT,
    ability TEXT,
    held_item TEXT DEFAULT 'none',
    is_shiny INTEGER DEFAULT 0,
    iv_hp INTEGER DEFAULT 15,
    iv_atk INTEGER DEFAULT 15,
    iv_def INTEGER DEFAULT 15,
    iv_spa INTEGER DEFAULT 15,
    iv_spd INTEGER DEFAULT 15,
    iv_spe INTEGER DEFAULT 15,
    ev_hp INTEGER DEFAULT 0,
    ev_atk INTEGER DEFAULT 0,
    ev_def INTEGER DEFAULT 0,
    ev_spa INTEGER DEFAULT 0,
    ev_spd INTEGER DEFAULT 0,
    ev_spe INTEGER DEFAULT 0,
    moves TEXT DEFAULT '[]',
    caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_pokemon_user ON user_pokemon(user_id);

CREATE TABLE IF NOT EXISTS user_inventory (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    quantity INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS encounters (
    encounter_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL,
    species_name TEXT NOT NULL,
    level INTEGER NOT NULL,
    is_shiny INTEGER DEFAULT 0,
    is_safari INTEGER DEFAULT 0,
    ivs TEXT NOT NULL,
    nature TEXT NOT NULL,
    gender TEXT NOT NULL,
    attempts_left INTEGER DEFAULT 3,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_encounters_user ON encounters(user_id);

CREATE TABLE IF NOT EXISTS safari_sessions (
    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    zone TEXT NOT NULL,
    balls_left INTEGER DEFAULT 30,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cooldowns (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, action)
);

CREATE TABLE IF NOT EXISTS processed_updates (
    update_id INTEGER PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def get_db_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(config.DATABASE_PATH, timeout=15.0)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA busy_timeout = 15000;")
    return conn

async def init_db():
    conn = await get_db_connection()
    try:
        await conn.executescript(INIT_SQL)
        await conn.commit()
    finally:
        await conn.close()
