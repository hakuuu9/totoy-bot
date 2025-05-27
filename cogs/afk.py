import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URL # Assuming config.py is in the same directory

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Using the 'users' collection for AFK data

    # --- Slash Command: /afk ---
    @app_commands.command(name="afk", description="Set yourself as AFK with an optional reason.")
    @app_commands.describe(reason="The reason for being AFK (optional).")
    async def afk_slash(self, interaction: discord.Interaction, reason: str = None):
        user_id = str(interaction.user.id)
        current_time = datetime.utcnow()

        # Update or insert user's AFK status
        self.db.update_one(
            {"_id": user_id},
            {"$set": {"afk": {"reason": reason, "time": current_time}}},
            upsert=True
        )

        afk_message = f"You are now AFK"
        if reason:
            afk_message += f": **{reason}**"
        afk_message += f". I'll let people know when they mention you."

        await interaction.response.send_message(f"✅ {afk_message}", ephemeral=False)
        
        # Optionally, change nickname to indicate AFK
        try:
            # Check if bot has permissions to change nickname
            if interaction.guild.me.guild_permissions.manage_nicknames:
                member = interaction.user
                if not member.nick or not member.nick.startswith("[AFK]"):
                    original_nick = member.nick if member.nick else member.name
                    await member.edit(nick=f"[AFK] {original_nick}")
            else:
                print(f"Bot lacks 'manage_nicknames' permission in guild {interaction.guild.name}")
        except discord.Forbidden:
            print(f"Bot lacks permissions to change nickname for {interaction.user.name} in {interaction.guild.name}.")
        except Exception as e:
            print(f"An error occurred while changing nickname: {e}")

    # --- Listener: on_message ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages and messages from DMs
        if message.author.bot or not message.guild:
            return

        user_id = str(message.author.id)
        user_data = self.db.find_one({"_id": user_id})

        # --- Check if the author of the message is AFK (to clear their status) ---
        if user_data and "afk" in user_data:
            # Clear AFK status
            self.db.update_one({"_id": user_id}, {"$unset": {"afk": ""}})
            
            # Remove [AFK] from nickname if present
            try:
                # Check if bot has permissions to change nickname
                if message.guild.me.guild_permissions.manage_nicknames:
                    member = message.author
                    if member.nick and member.nick.startswith("[AFK]"):
                        # Restore original nickname or remove [AFK] prefix
                        original_nick = member.nick[len("[AFK] "):]
                        await member.edit(nick=original_nick if original_nick else None) # Set to None to clear custom nick
                else:
                    print(f"Bot lacks 'manage_nicknames' permission to clear AFK nickname in guild {message.guild.name}")
            except discord.Forbidden:
                print(f"Bot lacks permissions to change nickname for {message.author.name} in {message.guild.name}.")
            except Exception as e:
                print(f"An error occurred while clearing AFK nickname: {e}")

            # Calculate AFK duration
            afk_time = user_data["afk"]["time"]
            duration = datetime.utcnow() - afk_time
            
            # Format duration nicely
            days = duration.days
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            duration_str = ""
            if days > 0:
                duration_str += f"{days} day{'s' if days > 1 else ''}, "
            if hours > 0:
                duration_str += f"{hours} hour{'s' if hours > 1 else ''}, "
            if minutes > 0:
                duration_str += f"{minutes} minute{'s' if minutes > 1 else ''}, "
            if not duration_str: # If less than a minute
                duration_str = "a few seconds"
            else:
                duration_str = duration_str.rstrip(', ') # Remove trailing comma and space

            await message.channel.send(f"Welcome back, {message.author.mention}! You were AFK for {duration_str}.")
            return # Don't process mentions if the author just came back from AFK

        # --- Check for mentions of AFK users ---
        for member in message.mentions:
            member_id = str(member.id)
            afk_data = self.db.find_one({"_id": member_id})

            if afk_data and "afk" in afk_data:
                reason = afk_data["afk"]["reason"]
                afk_time = afk_data["afk"]["time"]
                
                # Calculate AFK duration
                duration = datetime.utcnow() - afk_time
                
                # Format duration nicely
                days = duration.days
                hours, remainder = divmod(duration.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                duration_str = ""
                if days > 0:
                    duration_str += f"{days} day{'s' if days > 1 else ''}, "
                if hours > 0:
                    duration_str += f"{hours} hour{'s' if hours > 1 else ''}, "
                if minutes > 0:
                    duration_str += f"{minutes} minute{'s' if minutes > 1 else ''}, "
                if not duration_str: # If less than a minute
                    duration_str = "a few seconds"
                else:
                    duration_str = duration_str.rstrip(', ') # Remove trailing comma and space

                response = f"{member.mention} is AFK"
                if reason:
                    response += f" with reason: **{reason}**"
                response += f" (AFK for {duration_str})."
                
                await message.channel.send(response)
                # Only send one AFK response per message, even if multiple AFK users are mentioned
                return 

    def cog_unload(self):
        self.client.close()
        print("AFK MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(AFK(bot))