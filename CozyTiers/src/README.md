# CozyTier

A Discord bot for tier list testing and management.

## Setup

1. Install dependencies: `pip install -r requirements.txt`

2. Set up environment variables in `.env`:
   - DISCORD_TOKEN: Your bot token
   - DB_HOST, DB_USER, DB_PASSWORD, DB_NAME: MySQL database details

3. Run database setup: `python src/db_setup.py`

4. Run the bot: `python src/bot.py`

## Features

- Server registration with /register
- Tester applications via /apply
- Queue system for testing
- Tier assignment with /tier-set
- Role management for tiers (LT5 to HT1)

## Commands

- `/register`: Register server
- `/apply`: Apply to be tester
- `/approve <user_id>`: Approve application
- `/reject <user_id> <reason>`: Reject application
- `/join-queue`: Join testing queue
- `/available`: Mark as available tester
- `/complete-test <user>`: Complete a test
- `/review <tester> <rating> <comment>`: Review a tester
- `/tier-set <user> <tier>`: Assign tier to user
- `/set-points <role> <points>`: Set points for tier role