import discord
from discord.ext import commands
from config import DISCORD_TOKEN, DEBUG
import db_setup
from db_setup import close_db
import os

# Change working directory to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print("-=-=-=-=-=-=-=-=-=-")
    print(f"Bot Name: {bot.user.name}")
    print(f"User ID: {bot.user.id}")
    print(f"Servers: {len(bot.guilds)}")
    print(f"Commands: {len(bot.tree.get_commands())}")
    print(f"Debug: {'ON' if DEBUG else 'OFF'}")
    print("-=-=-=-=-=-=-=-=-=-")
    await bot.tree.sync()  # Sync slash commands

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if DEBUG and interaction.type == discord.InteractionType.application_command:
        command_name = interaction.command.name if hasattr(interaction, 'command') else 'Unknown'
        user = interaction.user
        guild = interaction.guild
        print(f"{user}({user.id}) executed {command_name} in {guild.name}({guild.id})")

@bot.event
async def on_close():
    """Clean up when bot closes"""
    close_db()

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