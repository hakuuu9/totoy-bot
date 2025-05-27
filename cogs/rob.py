import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from datetime import datetime, timedelta # Ensure datetime and timedelta are imported
from config import MONGO_URL # Assuming config.py is in the same directory

# Configuration for rob amounts and cooldown
ROB_COOLDOWN_HOURS = 24 # 1 day cooldown
MAX_ROB_AMOUNT = 200
MIN_ROB_AMOUNT = 1

# Custom rob emoji
ROB_EMOJI = "<a:rob:1376799725986119790>"

# IMPORTANT: Add the Anti-Rob emoji here as well, consistent with shop.py and use.py
ANTI_ROB_EMOJI = "<:antirob:1376801124656349214>"

# Scaling tiers for robbed amount based on target's balance
ROB_TIERS = {
    "very_low": {"max_balance": 50, "rob_min": 1, "rob_max": 20},
    "low": {"max_balance": 200, "rob_min": 1, "rob_max": 50},
    "medium": {"max_balance": 500, "rob_min": 1, "rob_max": 100},
    "high": {"max_balance": float('inf'), "rob_min": 1, "rob_max": MAX_ROB_AMOUNT} # float('inf') for effectively no upper limit
}

class Rob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the 'users' collection

    @app_commands.command(name="rob", description="Attempt to rob another member!")
    @app_commands.describe(target_member="The member you want to rob.")
    async def rob(self, interaction: discord.Interaction, target_member: discord.Member):
        robber_id = str(interaction.user.id)
        target_id = str(target_member.id)
        current_time = datetime.utcnow() # Use UTC time for consistency

        # Defer the response as we'll be interacting with the database and potentially waiting.
        await interaction.response.defer(ephemeral=False)

        # --- Initial Validations ---
        if interaction.user.id == target_member.id:
            return await interaction.followup.send("❌ You cannot rob yourself!", ephemeral=True)

        if target_member.bot:
            return await interaction.followup.send("❌ You cannot rob a bot!", ephemeral=True)

        # --- Fetch Robber's Data ---
        robber_data = self.db.find_one({"_id": robber_id})
        robber_balance = int(robber_data.get("balance", 0)) if robber_data else 0
        rob_cooldown_until = robber_data.get("rob_cooldown") if robber_data else None

        # --- Check Cooldown for Robber ---
        if rob_cooldown_until and current_time < rob_cooldown_until:
            remaining_time = rob_cooldown_until - current_time
            # Format cooldown message (days, hours, minutes)
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            cooldown_str = ""
            if remaining_time.days > 0:
                cooldown_str += f"{remaining_time.days} day{'s' if remaining_time.days > 1 else ''}"
            if hours > 0:
                if cooldown_str: cooldown_str += ", " # Add comma if there are preceding units
                cooldown_str += f"{hours} hour{'s' if hours > 1 else ''}"
            if minutes > 0:
                if cooldown_str: cooldown_str += ", "
                cooldown_str += f"{minutes} minute{'s' if minutes > 1 else ''}"
            
            cooldown_str = cooldown_str if cooldown_str else "a few seconds" # Fallback for very short times

            return await interaction.followup.send(
                f"⏳ You are on cooldown! You can rob again in **{cooldown_str}**.",
                ephemeral=True
            )

        # --- Fetch Target's Data ---
        target_data = self.db.find_one({"_id": target_id})
        target_balance = int(target_data.get("balance", 0)) if target_data else 0

        # --- NEW ADDITION: Check if target has active Anti-Rob protection ---
        target_anti_rob_expires_at = target_data.get("anti_rob_expires_at") if target_data else None
        if target_anti_rob_expires_at and current_time < target_anti_rob_expires_at:
            remaining_protection_time = target_anti_rob_expires_at - current_time
            hours, remainder = divmod(remaining_protection_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            protection_str = ""
            if remaining_protection_time.days > 0:
                protection_str += f"{remaining_protection_time.days} day{'s' if remaining_protection_time.days > 1 else ''}"
            if hours > 0:
                if protection_str: protection_str += ", "
                protection_str += f"{hours} hour{'s' if hours > 1 else ''}"
            if minutes > 0:
                if protection_str: protection_str += ", "
                protection_str += f"{minutes} minute{'s' if minutes > 1 else ''}"
            
            protection_str = protection_str if protection_str else "a few seconds"

            return await interaction.followup.send(
                f"🛡️ {target_member.mention} is currently protected by an {ANTI_ROB_EMOJI} **Anti-Rob Shield** "
                f"for another **{protection_str}**! You cannot rob them.",
                ephemeral=True
            )
        # --- END NEW ADDITION ---

        # --- Validate Target's Balance ---
        if target_balance <= 0: # Cannot rob if target has no money or negative balance
            return await interaction.followup.send(f"❌ {target_member.display_name} has no ₱ to rob!", ephemeral=True)
        
        # --- Determine Rob Amount based on Target's Balance ---
        rob_min_tier = MIN_ROB_AMOUNT
        rob_max_tier = MAX_ROB_AMOUNT

        for tier_name, tier_info in ROB_TIERS.items():
            if target_balance <= tier_info["max_balance"]:
                rob_min_tier = tier_info["rob_min"]
                rob_max_tier = tier_info["rob_max"]
                break # Found the appropriate tier

        # Ensure calculated range is valid
        rob_min_tier = max(MIN_ROB_AMOUNT, rob_min_tier)
        rob_max_tier = min(MAX_ROB_AMOUNT, rob_max_tier)
        
        # Make sure rob_min_tier isn't greater than rob_max_tier
        if rob_min_tier > rob_max_tier:
            rob_min_tier = rob_max_tier # Fallback if range is somehow inverted

        # Randomly choose amount to rob within the calculated tier, capping at target's current balance
        rob_amount = random.randint(rob_min_tier, rob_max_tier)
        rob_amount = min(rob_amount, target_balance) # Cannot rob more than target has

        if rob_amount <= 0: # This can happen if target_balance is very low (e.g., ₱1-₱10) and rob_max_tier is low.
             return await interaction.followup.send(f"❌ {target_member.display_name} is too poor to rob any meaningful amount!", ephemeral=True)

        # --- Perform the Robbery ---
        # Update robber's balance and set cooldown
        self.db.update_one(
            {"_id": robber_id},
            {"$inc": {"balance": rob_amount}, "$set": {"rob_cooldown": current_time + timedelta(hours=ROB_COOLDOWN_HOURS)}},
            upsert=True
        )

        # Update target's balance
        self.db.update_one(
            {"_id": target_id},
            {"$inc": {"balance": -rob_amount}},
            upsert=True # In case target has no document yet
        )

        new_robber_balance = robber_balance + rob_amount
        new_target_balance = target_balance - rob_amount

        await interaction.followup.send(
            f"{ROB_EMOJI} You successfully robbed ₱{rob_amount:,} from {target_member.mention}!\n"
            f"Your new balance: ₱{new_robber_balance:,}.\n"
            f"{target_member.display_name}'s new balance: ₱{new_target_balance:,}.\n"
            f"You are now on cooldown for {ROB_COOLDOWN_HOURS} hours."
        )

    def cog_unload(self):
        self.client.close()
        print("Rob MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Rob(bot))