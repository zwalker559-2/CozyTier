import discord
from discord.ext import commands
import mysql.connector
from config import DISCORD_TOKEN, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Database connection
db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = db.cursor()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()  # Sync slash commands

# Load cogs
async def load_cogs():
    await bot.load_extension('cogs.registration')
    await bot.load_extension('cogs.queue')
    await bot.load_extension('cogs.tier')
    await bot.load_extension('cogs.applications')

async def main():
    await load_cogs()
    await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())