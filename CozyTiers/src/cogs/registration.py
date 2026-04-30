import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
import json
import os
import asyncio
from db_setup import db, cursor, reconnect_db
from config import REGISTER_USER_IDS

class ChannelIdModal(Modal):
    def __init__(self, parent_view: View):
        super().__init__(title="Enter Channel ID")
        self.parent_view = parent_view
        self.channel_id = TextInput(label="Channel ID", placeholder="123456789012345678", required=True)
        self.add_item(self.channel_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            await interaction.response.send_message("That is not a valid channel ID.", ephemeral=True)
            return

        channel = self.parent_view.guild.get_channel(channel_id)
        if channel is None:
            await interaction.response.send_message("I couldn't find a channel with that ID in this guild.", ephemeral=True)
            return

        self.parent_view.selected_channel_id = channel_id
        await interaction.response.send_message(f"Selected channel <#{channel_id}>.", ephemeral=True)
        self.parent_view.stop()

class ChannelSelectView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.guild = guild
        self.selected_channel_id = None

        channel_options = []
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                channel_options.append(discord.SelectOption(label=channel.name, value=str(channel.id), description=f"ID: {channel.id}"))

        if channel_options:
            self.channel_select = Select(
                placeholder="Select a channel",
                min_values=1,
                max_values=1,
                options=channel_options,
            )
            self.channel_select.callback = self.select_channel
            self.add_item(self.channel_select)
        else:
            self.channel_select = None

    async def select_channel(self, interaction: discord.Interaction):
        self.selected_channel_id = int(self.channel_select.values[0])
        await interaction.response.send_message(f"Selected channel <#{self.selected_channel_id}>.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Manual ID", style=discord.ButtonStyle.secondary)
    async def manual_id(self, interaction: discord.Interaction, button: Button):
        modal = ChannelIdModal(self)
        await interaction.response.send_modal(modal)

class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def ask_text_answer(self, interaction: discord.Interaction, prompt_message: discord.Message, prompt: str):
        await prompt_message.edit(content=prompt)

        def check(m: discord.Message):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            reply = await self.bot.wait_for('message', check=check, timeout=300.0)
            await reply.delete()
            return reply.content
        except asyncio.TimeoutError:
            await interaction.followup.send("Registration timed out.", ephemeral=True)
            raise

    async def ask_channel(self, interaction: discord.Interaction, prompt: str):
        view = ChannelSelectView(interaction.guild)
        prompt_message = await interaction.followup.send(prompt, view=view)
        await view.wait()
        await prompt_message.edit(view=None)
        if view.selected_channel_id is None:
            raise asyncio.TimeoutError
        return view.selected_channel_id

    @app_commands.command(name="register", description="Register the server for CozyTier")
    async def register(self, interaction: discord.Interaction):
        if REGISTER_USER_IDS and interaction.user.id not in REGISTER_USER_IDS:
            await interaction.response.send_message("You are not authorized to run /register. Please ask a configured administrator.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You don't have permission to register this server. Only administrators or the server owner can do this.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            reconnect_db()
            cursor.execute("SELECT * FROM servers WHERE guild_id = %s", (interaction.guild.id,))
            if cursor.fetchone():
                await interaction.followup.send("This server is already registered.", ephemeral=True)
                return
        except Exception as e:
            await interaction.followup.send(f"Database error: {e}", ephemeral=True)
            return

        prompt_message = await interaction.followup.send("Starting server registration. Please answer the questions below.")

        try:
            listing_name = await self.ask_text_answer(interaction, prompt_message, "1️⃣ What is the listing name for this server?")
            listings_logo = await self.ask_text_answer(interaction, prompt_message, "2️⃣ What is the listings logo URL?")
            app_logs_channel = await self.ask_channel(interaction, "3️⃣ Select the application logs channel.")
            queue_channel_id = await self.ask_channel(interaction, "4️⃣ Select the queue channel where the Join Queue button should be posted.")
            application_staff_role = int(await self.ask_text_answer(interaction, prompt_message, "5️⃣ What is the role ID for application staff (can review and open tickets)?"))
            tier_staff_role = int(await self.ask_text_answer(interaction, prompt_message, "6️⃣ What is the tier management role ID for approve/deny/see applications?"))
        except asyncio.TimeoutError:
            return
        except ValueError:
            await interaction.followup.send("One of the role IDs was invalid. Please start registration again and provide numeric IDs.", ephemeral=True)
            return

        try:
            reconnect_db()
            cursor.execute("""
                INSERT INTO servers (guild_id, guild_name, guild_icon, owner_id, listing_name, listings_logo, app_logs_channel, tier_staff_role, application_staff_role, queue_channel_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                interaction.guild.id,
                interaction.guild.name,
                interaction.guild.icon.url if interaction.guild.icon else None,
                interaction.guild.owner.id,
                listing_name,
                listings_logo,
                app_logs_channel,
                tier_staff_role,
                application_staff_role,
                queue_channel_id,
            ))
            db.commit()
        except Exception as e:
            await interaction.followup.send(f"Failed to save to database: {e}", ephemeral=True)
            return

        server_folder = os.path.join(os.path.dirname(__file__), '..', 'data', str(interaction.guild.id))
        os.makedirs(server_folder, exist_ok=True)
        server_data = {
            "guild_id": interaction.guild.id,
            "guild_name": interaction.guild.name,
            "guild_icon": interaction.guild.icon.url if interaction.guild.icon else None,
            "owner_id": interaction.guild.owner.id,
            "listing_name": listing_name,
            "listings_logo": listings_logo,
            "app_logs_channel": app_logs_channel,
            "tier_staff_role": tier_staff_role,
            "application_staff_role": application_staff_role,
            "queue_channel_id": queue_channel_id,
        }
        try:
            with open(f"{server_folder}/servers.json", "w") as f:
                json.dump(server_data, f, indent=4)
        except Exception as e:
            await interaction.followup.send(f"Failed to save server data: {e}", ephemeral=True)
            return

        queue_channel = interaction.guild.get_channel(queue_channel_id)
        if queue_channel:
            from cogs.queue import JoinQueueView
            queue_embed = discord.Embed(
                title="Join Queue",
                description="Click the button below to join the queue if you have the verified role.",
                color=discord.Color.blurple()
            )
            await queue_channel.send(embed=queue_embed, view=JoinQueueView())

        summary_embed = discord.Embed(
            title="Server Registered Successfully",
            description="This server is now configured for CozyTier.",
            color=discord.Color.green()
        )
        summary_embed.set_thumbnail(url=listings_logo)
        summary_embed.add_field(name="Listing Name", value=listing_name, inline=True)
        summary_embed.add_field(name="Guild", value=f"{interaction.guild.name} ({interaction.guild.id})", inline=True)
        summary_embed.add_field(name="Owner", value=f"<@{interaction.guild.owner.id>}", inline=True)
        summary_embed.add_field(name="Application Logs Channel", value=f"<#{app_logs_channel}>\n{app_logs_channel}", inline=False)
        summary_embed.add_field(name="Queue Channel", value=f"<#{queue_channel_id}>\n{queue_channel_id}", inline=False)
        summary_embed.add_field(name="Application Staff Role", value=f"<@&{application_staff_role}>\n{application_staff_role}", inline=True)
        summary_embed.add_field(name="Tier Management Role", value=f"<@&{tier_staff_role}>\n{tier_staff_role}", inline=True)
        summary_embed.set_footer(text="Keep your server configuration IDs safe.")

        await interaction.followup.send(embed=summary_embed)

        roles = ["LT5", "LT4", "LT3", "LT2", "LT1", "HT5", "HT4", "HT3", "HT2", "HT1"]
        points = [0] * len(roles)
        tier_roles = []
        for i, role_name in enumerate(roles):
            try:
                role = await interaction.guild.create_role(name=role_name, color=discord.Color.blue())
            except Exception as e:
                await interaction.followup.send(f"Failed to create role {role_name}: {e}", ephemeral=True)
                continue
            try:
                reconnect_db()
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