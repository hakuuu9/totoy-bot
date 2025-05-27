import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from datetime import datetime, timedelta # Needed for checking Anti-Rob expiry
from config import MONGO_URL # Assuming config.py is in the same directory

# Re-use emojis for consistency across commands
CHICKEN_EMOJI = "<:chickenshop:1376780896149176420>"
ANTI_ROB_EMOJI = "<:antirob:1376801124656349214>"

class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the 'users' collection

    @app_commands.command(name="inventory", description="View your owned items and protection status.")
    async def inventory(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        current_time = datetime.utcnow() # Use UTC time for comparison with expiry dates

        # Defer the response as we'll be interacting with the database
        await interaction.response.defer(ephemeral=False)

        user_data = self.db.find_one({"_id": user_id})

        # Get user's data, defaulting to 0 or None if not found
        balance = int(user_data.get("balance", 0)) if user_data else 0
        chickens_owned = int(user_data.get("chickens_owned", 0)) if user_data else 0
        anti_rob_items_owned = int(user_data.get("anti_rob_items", 0)) if user_data else 0
        anti_rob_expires_at = user_data.get("anti_rob_expires_at") if user_data else None

        # --- Format Anti-Rob Protection Status ---
        anti_rob_status = ""
        if anti_rob_expires_at and current_time < anti_rob_expires_at:
            # Protection is active, calculate remaining time
            remaining_time = anti_rob_expires_at - current_time
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            time_str = ""
            if remaining_time.days > 0:
                time_str += f"{remaining_time.days} day{'s' if remaining_time.days > 1 else ''}"
            if hours > 0:
                if time_str: time_str += ", "
                time_str += f"{hours} hour{'s' if hours > 1 else ''}"
            if minutes > 0:
                if time_str: time_str += ", "
                time_str += f"{minutes} minute{'s' if minutes > 1 else ''}"
            
            time_str = time_str if time_str else "a few seconds"
            
            anti_rob_status = f"Active! Ends in **{time_str}** (<t:{int(anti_rob_expires_at.timestamp())}:R>)" # Relative timestamp
        else:
            anti_rob_status = "Inactive"
            # Optional: If the expiry time is in the past, clear it from DB to keep it clean
            if anti_rob_expires_at and current_time >= anti_rob_expires_at:
                self.db.update_one({"_id": user_id}, {"$unset": {"anti_rob_expires_at": ""}})

        # --- Create the Embed ---
        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory 🎒",
            color=discord.Color.blue() # A nice blue color for inventory
        )
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.set_footer(text="Manage your assets wisely!")

        # Add fields
        embed.add_field(name="💰 Cash", value=f"₱{balance:,}", inline=True)
        embed.add_field(name="🐔 Chickens", value=f"{chickens_owned} {CHICKEN_EMOJI}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True) # Invisible field for spacing

        embed.add_field(name=f"{ANTI_ROB_EMOJI} Anti-Rob Shields", value=f"{anti_rob_items_owned} owned", inline=False)
        embed.add_field(name="🛡️ Anti-Rob Protection Status", value=anti_rob_status, inline=False)

        await interaction.followup.send(embed=embed)

    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("Inventory MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Inventory(bot))