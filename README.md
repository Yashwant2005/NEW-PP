# NEW-PP
## PokePlay Telegram Serverless Pokémon Game Bot

A high-performance, modular, and serverless Telegram Pokémon game bot built from scratch in Python with `aiogram` and ASGI webhook support.

### Features
- **`/start`**: Trainer onboarding, starter Pokémon selection (Bulbasaur, Charmander, Squirtle), trainer profiles, and interactive navigation menus.
- **`/hunt`**: Regional wild encounters, rarity tiers, shiny rates, ball throwing mechanics (Regular, Great, Ultra, Master), flee logic, and cooldown tracking.
- **`/mybag`**: Dynamic trainer inventory with category filtering (Balls, Stones, Candies, Medicine, Key items).
- **`/mypokemon`**: Owned Pokémon list with pagination (10 per page), IV/Level/Recent sorting, and individual Pokémon attribute viewing.
- **Safari System**:
  - `/safari_zone`: Zone selection (10 regions) and status overview.
  - `/claim_safari_pass`: Free daily Safari Pass claim with UTC midnight reset.
  - `/enter` & `/exit`: Safari session tracking and 30 Safari Balls allocation.
  - Safari hunting with exclusive rare encounter rates and custom catch/flee rules.

### Running & Deploying Serverless

1. **Environment Variables**:
   Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```

2. **Run Webhook Server Locally or in Cloud**:
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000
   ```

3. **Run Test Suite**:
   ```bash
   PYTHONPATH=. pytest -o asyncio_mode=auto tests/
   ```
