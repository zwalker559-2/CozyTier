import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import json
import os
import asyncio
from db_setup import db, cursor, reconnect_db

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="apply", description="Apply to become a tester")
    async def apply(self, interaction: discord.Interaction):
        # Check if already applied
        try:
            reconnect_db()
            cursor.execute("SELECT * FROM testers WHERE user_id = %s AND guild_id = %s", (interaction.user.id, interaction.guild.id))
            if cursor.fetchone():
                await interaction.response.send_message("You have already applied.", ephemeral=True)
                return
        except Exception as e:
            await interaction.response.send_message(f"Error checking application: {e}", ephemeral=True)
            return

        # Start DM application
        try:
            dm_channel = await interaction.user.create_dm()
        except:
            await interaction.response.send_message("I can't DM you. Please enable DMs.", ephemeral=True)
            return

        await interaction.response.send_message("Check your DMs to start the application.", ephemeral=True)

        # First question: Region
        view = RegionView(self.bot, interaction.guild.id, dm_channel, interaction.user.id)
        await dm_channel.send("What region are you in?", view=view)

class RegionView(View):
    def __init__(self, bot, guild_id, dm_channel, user_id):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.dm_channel = dm_channel
        self.user_id = user_id

    @discord.ui.button(label="NA", style=discord.ButtonStyle.primary)
    async def na_button(self, interaction: discord.Interaction, button: Button):
        await self.select_region(interaction, "NA")

    @discord.ui.button(label="EU", style=discord.ButtonStyle.primary)
    async def eu_button(self, interaction: discord.Interaction, button: Button):
        await self.select_region(interaction, "EU")

    async def select_region(self, interaction, region):
        self.region = region
        await interaction.response.send_message(f"Region selected: {region}")

        # Next question: Stand out
        view = StandoutView(self.bot, self.guild_id, self.dm_channel, self.user_id, self.region)
        await self.dm_channel.send("What makes you stand out?", view=view)

class StandoutView(View):
    def __init__(self, bot, guild_id, dm_channel, user_id, region):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.dm_channel = dm_channel
        self.user_id = user_id
        self.region = region

    @discord.ui.button(label="ANSWER", style=discord.ButtonStyle.primary)
    async def answer_button(self, interaction: discord.Interaction, button: Button):
        modal = StandoutModal(self.bot, self.guild_id, self.dm_channel, self.user_id, self.region)
        await interaction.response.send_modal(modal)

class StandoutModal(Modal):
    def __init__(self, bot, guild_id, dm_channel, user_id, region):
        super().__init__(title="What makes you stand out?")
        self.bot = bot
        self.guild_id = guild_id
        self.dm_channel = dm_channel
        self.user_id = user_id
        self.region = region

        self.standout_input = TextInput(label="Your answer", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.standout_input)

    async def on_submit(self, interaction: discord.Interaction):
        standout = self.standout_input.value

        # Save application
        try:
            reconnect_db()
            cursor.execute("""
                INSERT INTO testers (guild_id, user_id, region, standout, status)
                VALUES (%s, %s, %s, %s, 'pending')
            """, (self.guild_id, self.user_id, self.region, standout))
            db.commit()
        except Exception as e:
            await interaction.response.send_message(f"Error saving application: {e}", ephemeral=True)
            return

        # Log in server
        server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(self.guild_id))
        os.makedirs(server_folder, exist_ok=True)
        testers_file = f"{server_folder}/testers.json"
        if os.path.exists(testers_file):
            with open(testers_file, "r") as f:
                testers = json.load(f)
        else:
            testers = []

        testers.append({
            "user_id": self.user_id,
            "region": self.region,
            "standout": standout,
            "status": "pending"
        })

        with open(testers_file, "w") as f:
            json.dump(testers, f, indent=4)

        # Get app logs channel
        cursor.execute("SELECT app_logs_channel FROM servers WHERE guild_id = %s", (self.guild_id,))
        result = cursor.fetchone()
        if result:
            channel = self.bot.get_channel(result[0])
            if channel:
                embed = discord.Embed(title="New Tester Application", color=discord.Color.blue())
                embed.add_field(name="User", value=f"<@{self.user_id}>", inline=True)
                embed.add_field(name="Region", value=self.region, inline=True)
                embed.add_field(name="Standout", value=standout, inline=False)
                await channel.send(embed=embed)

class ApplicationsApproveReject(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="approve", description="Approve a tester application")
    @app_commands.describe(user_id="The user ID to approve")
    async def approve(self, interaction: discord.Interaction, user_id: str):
        try:
            # Check permission
            reconnect_db()
            cursor.execute("SELECT tier_staff_role FROM servers WHERE guild_id = %s", (interaction.guild.id,))
            result = cursor.fetchone()
            if not result or result[0] not in [role.id for role in interaction.user.roles]:
                await interaction.response.send_message("You don't have permission.", ephemeral=True)
                return

            user_id = int(user_id)

            # Update status
            cursor.execute("UPDATE testers SET status = 'approved', tester_tier = 'LT5' WHERE user_id = %s AND guild_id = %s", (user_id, interaction.guild.id))
            db.commit()

            # Update json
            server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(interaction.guild.id))
            testers_file = f"{server_folder}/testers.json"
            if os.path.exists(testers_file):
                with open(testers_file, "r") as f:
                    testers = json.load(f)
                for tester in testers:
                    if tester["user_id"] == user_id:
                        tester["status"] = "approved"
                        tester["tester_tier"] = "LT5"
                        tester["completed_tests"] = 0
                with open(testers_file, "w") as f:
                    json.dump(testers, f, indent=4)

            # DM user
            user = self.bot.get_user(user_id)
            if user:
                await user.send("Your application has been approved! Here are the instructions: [instructions here]")

            await interaction.response.send_message("Application approved.")
        except Exception as e:
            await interaction.response.send_message(f"Error approving application: {e}", ephemeral=True)

    @app_commands.command(name="reject", description="Reject a tester application")
    @app_commands.describe(user_id="The user ID to reject", reason="The reason for rejection")
    async def reject(self, interaction: discord.Interaction, user_id: str, reason: str):
        try:
            # Check permission
            reconnect_db()
            cursor.execute("SELECT tier_staff_role FROM servers WHERE guild_id = %s", (interaction.guild.id,))
            result = cursor.fetchone()
            if not result or result[0] not in [role.id for role in interaction.user.roles]:
                await interaction.response.send_message("You don't have permission.", ephemeral=True)
                return

            user_id = int(user_id)

            # Update status
            cursor.execute("UPDATE testers SET status = 'rejected', reason = %s WHERE user_id = %s AND guild_id = %s", (reason, user_id, interaction.guild.id))
            db.commit()

            # Update json
            server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(interaction.guild.id))
            testers_file = f"{server_folder}/testers.json"
            if os.path.exists(testers_file):
                with open(testers_file, "r") as f:
                    testers = json.load(f)
                for tester in testers:
                    if tester["user_id"] == user_id:
                        tester["status"] = "rejected"
                        tester["reason"] = reason
                with open(testers_file, "w") as f:
                    json.dump(testers, f, indent=4)

            # DM user
            user = self.bot.get_user(user_id)
            if user:
                await user.send(f"Your application has been rejected. Reason: {reason}. Thanks for being part of Cozy Tiers!")

            await interaction.response.send_message("Application rejected.")
        except Exception as e:
            await interaction.response.send_message(f"Error rejecting application: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Applications(bot))
    await bot.add_cog(ApplicationsApproveReject(bot))