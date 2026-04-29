import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from db_setup import db, cursor, reconnect_db

class Tier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tier-set", description="Set a user's tier")
    @app_commands.describe(user="The user to set tier for", tier="The tier to assign")
    async def tier_set(self, interaction: discord.Interaction, user: discord.Member, tier: str):
        # Check if tester
        try:
            reconnect_db()
            cursor.execute("SELECT * FROM testers WHERE user_id = %s AND guild_id = %s AND status = 'approved'", (interaction.user.id, interaction.guild.id))
            if not cursor.fetchone():
                await interaction.response.send_message("You are not an approved tester.", ephemeral=True)
                return

            # Get tier role
            cursor.execute("SELECT role_id FROM tier_roles WHERE guild_id = %s AND role_name = %s", (interaction.guild.id, tier))
            result = cursor.fetchone()
            if not result:
                await interaction.response.send_message("Tier not found.", ephemeral=True)
                return

            role_id = result[0]
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message("Role not found.", ephemeral=True)
                return

            # Assign role
            await user.add_roles(role)

            # Save to DB
            reconnect_db()
            cursor.execute("""
                INSERT INTO tiers (guild_id, user_id, tier, role_id)
                VALUES (%s, %s, %s, %s)
            """, (interaction.guild.id, user.id, tier, role_id))
            db.commit()
        except Exception as e:
            await interaction.response.send_message(f"Error setting tier: {e}", ephemeral=True)
            return

        # Save to tier.json
        server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(interaction.guild.id))
        os.makedirs(server_folder, exist_ok=True)
        tier_file = f"{server_folder}/tier.json"
        if os.path.exists(tier_file):
            with open(tier_file, "r") as f:
                tiers = json.load(f)
        else:
            tiers = []

        tiers.append({
            "user_id": user.id,
            "user_name": user.name,
            "tier": tier,
            "role_id": role_id
        })

        with open(tier_file, "w") as f:
            json.dump(tiers, f, indent=4)

        await interaction.response.send_message(f"Tier {tier} assigned to {user.mention}.")

async def setup(bot):
    await bot.add_cog(Tier(bot))