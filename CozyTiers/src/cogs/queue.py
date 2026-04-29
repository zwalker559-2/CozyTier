import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from db_setup import db, cursor

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_check.start()

    def get_user_tier_points(self, guild_id, user_id):
        # Get user's highest tier points
        cursor.execute("""
            SELECT tr.points FROM tiers t
            JOIN tier_roles tr ON t.tier = tr.role_name AND t.guild_id = tr.guild_id
            WHERE t.guild_id = %s AND t.user_id = %s
            ORDER BY tr.points DESC LIMIT 1
        """, (guild_id, user_id))
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_tester_tier_points(self, guild_id, tester_id):
        cursor.execute("SELECT tester_tier FROM testers WHERE guild_id = %s AND user_id = %s", (guild_id, tester_id))
        result = cursor.fetchone()
        if result:
            tier_name = result[0]
            cursor.execute("SELECT points FROM tier_roles WHERE guild_id = %s AND role_name = %s", (guild_id, tier_name))
            res = cursor.fetchone()
            return res[0] if res else 0
        return 0

    def get_tester_seniority(self, guild_id, tester_id):
        cursor.execute("SELECT completed_tests FROM testers WHERE guild_id = %s AND user_id = %s", (guild_id, tester_id))
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_tester_avg_review(self, guild_id, tester_id):
        cursor.execute("SELECT AVG(rating) FROM reviews WHERE guild_id = %s AND tester_id = %s", (guild_id, tester_id))
        result = cursor.fetchone()
        return result[0] if result and result[0] else 0

    @app_commands.command(name="join-queue", description="Join the testing queue")
    async def join_queue(self, interaction: discord.Interaction):
        # Check if already in queue
        cursor.execute("SELECT * FROM queue WHERE user_id = %s AND guild_id = %s AND status = 'waiting'", (interaction.user.id, interaction.guild.id))
        if cursor.fetchone():
            await interaction.response.send_message("You are already in the queue.", ephemeral=True)
            return

        # Add to queue
        cursor.execute("""
            INSERT INTO queue (guild_id, user_id, status)
            VALUES (%s, %s, 'waiting')
        """, (interaction.guild.id, interaction.user.id))
        db.commit()

        await interaction.response.send_message("Joined the queue.")

    @app_commands.command(name="available", description="Mark as available tester")
    async def available(self, interaction: discord.Interaction):
        # Check if tester
        cursor.execute("SELECT * FROM testers WHERE user_id = %s AND guild_id = %s AND status = 'approved'", (interaction.user.id, interaction.guild.id))
        if not cursor.fetchone():
            await interaction.response.send_message("You are not an approved tester.", ephemeral=True)
            return

        # Mark as available (perhaps a separate table or field)
        # For simplicity, assume testers are always available or add a field
        await interaction.response.send_message("Marked as available.")

    @tasks.loop(seconds=60)  # Check every minute
    async def queue_check(self):
        # Get all guilds
        cursor.execute("SELECT guild_id FROM servers")
        guilds = cursor.fetchall()

        for (guild_id,) in guilds:
            # Get waiting users
            cursor.execute("SELECT user_id FROM queue WHERE guild_id = %s AND status = 'waiting' ORDER BY id", (guild_id,))
            waiting_users = [row[0] for row in cursor.fetchall()]

            # Get available testers
            # Assume all approved testers are available for now
            cursor.execute("SELECT user_id FROM testers WHERE guild_id = %s AND status = 'approved'", (guild_id,))
            available_testers = [row[0] for row in cursor.fetchall()]

            if not waiting_users or not available_testers:
                continue

            num_testers = len(available_testers)

            if num_testers >= 3:
                # Advanced pairing logic
                for user in waiting_users[:num_testers]:  # Pair up to number of testers
                    user_tier = self.get_user_tier_points(guild_id, user)
                    
                    # Find suitable testers: same tier or one above
                    suitable_testers = []
                    for tester in available_testers:
                        tester_tier = self.get_tester_tier_points(guild_id, tester)
                        if tester_tier >= user_tier and tester_tier <= user_tier + 1:  # Same or one above (assuming points increase)
                            seniority = self.get_tester_seniority(guild_id, tester)
                            avg_review = self.get_tester_avg_review(guild_id, tester)
                            score = (tester_tier - user_tier) * 10 + seniority * 2 + avg_review * 5  # Weighted score
                            suitable_testers.append((tester, score))
                    
                    if suitable_testers:
                        # Sort by score descending
                        suitable_testers.sort(key=lambda x: x[1], reverse=True)
                        best_tester = suitable_testers[0][0]
                        
                        # Assign
                        cursor.execute("UPDATE queue SET tester_id = %s, status = 'assigned' WHERE user_id = %s AND guild_id = %s", (best_tester, user, guild_id))
                        db.commit()
                        
                        guild = self.bot.get_guild(guild_id)
                        user_obj = guild.get_member(user)
                        tester_obj = guild.get_member(best_tester)
                        if user_obj and tester_obj:
                            await user_obj.send(f"You have been paired with tester {tester_obj.name}")
                            await tester_obj.send(f"You have been assigned to test {user_obj.name}")
                        
                        available_testers.remove(best_tester)  # Remove from available for this round

            elif num_testers == 1:
                # Assign highest in queue
                user = waiting_users[0]
                tester = available_testers[0]

                cursor.execute("UPDATE queue SET tester_id = %s, status = 'assigned' WHERE user_id = %s AND guild_id = %s", (tester, user, guild_id))
                db.commit()

                guild = self.bot.get_guild(guild_id)
                user_obj = guild.get_member(user)
                tester_obj = guild.get_member(tester)
                if user_obj and tester_obj:
                    await user_obj.send(f"You have been paired with tester {tester_obj.name}")
                    await tester_obj.send(f"You have been assigned to test {user_obj.name}")

    @app_commands.command(name="complete-test", description="Complete a test")
    @app_commands.describe(user="The user whose test is completed")
    async def complete_test(self, interaction: discord.Interaction, user: discord.Member):
        # Check if tester
        cursor.execute("SELECT * FROM testers WHERE user_id = %s AND guild_id = %s AND status = 'approved'", (interaction.user.id, interaction.guild.id))
        if not cursor.fetchone():
            await interaction.response.send_message("You are not an approved tester.", ephemeral=True)
            return

        # Check if assigned to this user
        cursor.execute("SELECT * FROM queue WHERE user_id = %s AND tester_id = %s AND guild_id = %s AND status = 'assigned'", (user.id, interaction.user.id, interaction.guild.id))
        if not cursor.fetchone():
            await interaction.response.send_message("You are not assigned to this user.", ephemeral=True)
            return

        # Update status to completed
        cursor.execute("UPDATE queue SET status = 'completed' WHERE user_id = %s AND tester_id = %s AND guild_id = %s", (user.id, interaction.user.id, interaction.guild.id))
        db.commit()

        # Increment tester's completed tests
        cursor.execute("UPDATE testers SET completed_tests = completed_tests + 1 WHERE user_id = %s AND guild_id = %s", (interaction.user.id, interaction.guild.id))
        db.commit()

        # Delete queue entry after completion
        cursor.execute("DELETE FROM queue WHERE user_id = %s AND tester_id = %s AND guild_id = %s", (user.id, interaction.user.id, interaction.guild.id))
        db.commit()

        await interaction.response.send_message(f"Test completed for {user.mention}. They can now review you.")

    @app_commands.command(name="review", description="Review a tester")
    @app_commands.describe(tester="The tester to review", rating="Rating 1-5", comment="Optional comment")
    async def review(self, interaction: discord.Interaction, tester: discord.Member, rating: int, comment: str = ""):
        if not 1 <= rating <= 5:
            await interaction.response.send_message("Rating must be 1-5.", ephemeral=True)
            return

        # Check if tester is approved
        cursor.execute("SELECT * FROM testers WHERE user_id = %s AND guild_id = %s AND status = 'approved'", (tester.id, interaction.guild.id))
        if not cursor.fetchone():
            await interaction.response.send_message("Not a valid tester.", ephemeral=True)
            return

        # Add review
        cursor.execute("""
            INSERT INTO reviews (guild_id, user_id, tester_id, rating, comment)
            VALUES (%s, %s, %s, %s, %s)
        """, (interaction.guild.id, interaction.user.id, tester.id, rating, comment))
        db.commit()

        await interaction.response.send_message("Review submitted.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Queue(bot))