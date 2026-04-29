import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
from db_setup import db, cursor

class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register the server for CozyTier")
    async def register(self, interaction: discord.Interaction):
        # Check permissions: only server owner or administrators
        if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner.id:
            await interaction.response.send_message("You don't have permission to register this server. Only administrators or the server owner can do this.", ephemeral=True)
            return

        # Send immediate response to prevent timeout
        await interaction.response.defer()
        
        # Check if already registered
        try:
            cursor.execute("SELECT * FROM servers WHERE guild_id = %s", (interaction.guild.id,))
            if cursor.fetchone():
                await interaction.followup.send("This server is already registered.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"Database error: {e}", ephemeral=True)
            return

        # Start registration process
        await interaction.followup.send("Starting server registration. Please provide the following information:")

        # Ask for Listing Name
        await interaction.followup.send("What is the listing name for this server?")
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300.0)
            listing_name = msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("Registration timed out.")
            return

        # Ask for Listings Logo
        await interaction.followup.send("What is the listings logo URL?")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300.0)
            listings_logo = msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("Registration timed out.")
            return

        # Ask for Channel ID for Application Logs
        await interaction.followup.send("What is the channel ID for application logs?")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300.0)
            app_logs_channel = int(msg.content)
        except (asyncio.TimeoutError, ValueError):
            await interaction.followup.send("Invalid channel ID or timed out.")
            return

        # Ask for Role ID for TierStaff
        await interaction.followup.send("What is the role ID for TierStaff?")
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300.0)
            tier_staff_role = int(msg.content)
        except (asyncio.TimeoutError, ValueError):
            await interaction.followup.send("Invalid role ID or timed out.")
            return

        # Save to DB
        try:
            cursor.execute("""
                INSERT INTO servers (guild_id, guild_name, guild_icon, owner_id, listing_name, listings_logo, app_logs_channel, tier_staff_role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (interaction.guild.id, interaction.guild.name, interaction.guild.icon.url if interaction.guild.icon else None, interaction.guild.owner.id, listing_name, listings_logo, app_logs_channel, tier_staff_role))
            db.commit()
        except Exception as e:
            await interaction.followup.send(f"Failed to save to database: {e}", ephemeral=True)
            return

        # Create server folder
        server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(interaction.guild.id))
        os.makedirs(server_folder, exist_ok=True)

        # Save to servers.json
        server_data = {
            "guild_id": interaction.guild.id,
            "guild_name": interaction.guild.name,
            "guild_icon": interaction.guild.icon.url if interaction.guild.icon else None,
            "owner_id": interaction.guild.owner.id,
            "listing_name": listing_name,
            "listings_logo": listings_logo,
            "app_logs_channel": app_logs_channel,
            "tier_staff_role": tier_staff_role
        }
        try:
            with open(f"{server_folder}/servers.json", "w") as f:
                json.dump(server_data, f, indent=4)
        except Exception as e:
            await interaction.followup.send(f"Failed to save server data: {e}", ephemeral=True)
            return

        await interaction.followup.send("Server registered successfully!")

        # Create default tier roles
        roles = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]
        points = [0] * len(roles)
        tier_roles = []
        for i, role_name in enumerate(roles):
            try:
                role = await interaction.guild.create_role(name=role_name, color=discord.Color.blue())
            except Exception as e:
                await interaction.followup.send(f"Failed to create role {role_name}: {e}", ephemeral=True)
                continue

            # Save to DB with default points
            try:
                cursor.execute("""
                    INSERT INTO tier_roles (guild_id, role_name, role_id, points)
                    VALUES (%s, %s, %s, %s)
                """, (interaction.guild.id, role_name, role.id, points[i]))
                db.commit()
            except Exception as e:
                await interaction.followup.send(f"Failed to save role {role_name} to database: {e}", ephemeral=True)
                continue

            tier_roles.append({
                "role_name": role_name,
                "role_id": role.id,
                "points": points[i]
            })

        # Save to json
        tier_roles_file = f"{server_folder}/tier-roles.json"
        try:
            with open(tier_roles_file, "w") as f:
                json.dump(tier_roles, f, indent=4)
        except Exception as e:
            await interaction.followup.send(f"Failed to save tier roles: {e}", ephemeral=True)
            return

        await interaction.followup.send("Default tier roles created. Use /set-points to assign point values.")

async def setup(bot):
    await bot.add_cog(Registration(bot))