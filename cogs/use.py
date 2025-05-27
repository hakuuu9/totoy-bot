import discord
from discord.ext import commands
from discord import app_commands
import random
from pymongo import MongoClient
from datetime import datetime, timedelta
from config import MONGO_URL # Assuming config.py is in the same directory

# Re-use Anti-Rob emoji from shop.py for consistency
ANTI_ROB_EMOJI = "<:antirob:1376801124656349214>"

class Use(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the 'users' collection

    @app_commands.command(name="use", description="Use an item from your inventory.")
    @app_commands.describe(item="The item you wish to use.")
    @app_commands.choices(
        item=[
            app_commands.Choice(name="Anti-Rob Shield", value="anti-rob"),
            # Add more usable items here as your bot grows
        ]
    )
    async def use_item(self, interaction: discord.Interaction, item: str):
        user_id = str(interaction.user.id)
        current_time = datetime.utcnow()

        # Defer the response immediately
        await interaction.response.defer(ephemeral=False)

        user_data = self.db.find_one({"_id": user_id})
        
        # Initialize item counts for safety
        anti_rob_items_owned = int(user_data.get("anti_rob_items", 0)) if user_data else 0
        
        # Get existing anti-rob expiry time if any
        anti_rob_expires_at = user_data.get("anti_rob_expires_at") if user_data else None

        if item == "anti-rob":
            # --- Check if user owns Anti-Rob Shields ---
            if anti_rob_items_owned <= 0:
                return await interaction.followup.send(
                    f"❌ You don't have any {ANTI_ROB_EMOJI} **Anti-Rob Shield(s)** to use! Buy them from `/shop`.",
                    ephemeral=True
                )
            
            # --- Check if Anti-Rob protection is already active ---
            if anti_rob_expires_at and current_time < anti_rob_expires_at:
                remaining_time = anti_rob_expires_at - current_time
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                # Format remaining time
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

                return await interaction.followup.send(
                    f"⏳ Your {ANTI_ROB_EMOJI} **Anti-Rob Shield** is already active for another **{time_str}**!",
                    ephemeral=True
                )

            # --- Use Anti-Rob Shield ---
            # Random duration: 1, 2, or 3 days
            protection_days = random.randint(1, 3)
            new_expiry_time = current_time + timedelta(days=protection_days)

            # Update database: Decrement anti_rob_items and set expiry time
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"anti_rob_items": -1}, "$set": {"anti_rob_expires_at": new_expiry_time}},
                upsert=True # Upsert for safety, though user should exist from prior commands
            )

            new_anti_rob_items_owned = anti_rob_items_owned - 1

            await interaction.followup.send(
                f"✅ You used one {ANTI_ROB_EMOJI} **Anti-Rob Shield**!\n"
                f"You are now protected from being robbed for **{protection_days} day{'s' if protection_days > 1 else ''}**."
                f"Protection expires on: <t:{int(new_expiry_time.timestamp())}:F> (Discord Timestamp)\n" # Discord timestamp
                f"You have {new_anti_rob_items_owned} {ANTI_ROB_EMOJI} Anti-Rob Shield(s) left."
            )

        else:
            # Handle other items here if you add them later
            await interaction.followup.send(
                f"❌ The item '{item}' is not a usable item, or its use functionality is not yet implemented.",
                ephemeral=True
            )

    def cog_unload(self):
        self.client.close()
        print("Use MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Use(bot))