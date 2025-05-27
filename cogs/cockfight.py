import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from config import MONGO_URL # Assuming config.py is in the same directory

# Re-use emojis from previous commands for consistency
CHICKEN_EMOJI = "<:chickenshop:1376780896149176420>"
WIN_EMOJI = "<:win_cf:1376735656042299483>"
LOSE_EMOJI = "<:lose_cf:1376735674132332574>"
FIGHT_EMOJI = "⚔️" # Default fight emoji. Replace if you have a custom one (e.g., "<:your_fight_emoji:ID>")

class Cockfight(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the same 'users' collection where balance and chickens are stored

    @app_commands.command(name="cockfight", description="Bet an amount of ₱ on a cockfight!") # Updated description
    @app_commands.describe(bet_amount="The amount of ₱ to bet.") # Updated argument description
    async def cockfight(self, interaction: discord.Interaction, bet_amount: int):
        user_id = str(interaction.user.id)

        # Defer the response immediately to prevent timeout, as this command involves a delay and DB interaction.
        await interaction.response.defer(ephemeral=False)

        # Fetch user data (balance and chickens owned)
        user_data = self.db.find_one({"_id": user_id})
        current_balance = int(user_data.get("balance", 0)) if user_data else 0
        chickens_owned = int(user_data.get("chickens_owned", 0)) if user_data else 0

        # --- Input Validation ---
        if bet_amount <= 0:
            return await interaction.followup.send("❌ You must bet a positive amount.", ephemeral=True)

        if current_balance < bet_amount:
            return await interaction.followup.send(
                f"❌ You don't have enough money! You have ₱{current_balance:,} but tried to bet ₱{bet_amount:,}.",
                ephemeral=True
            )

        if chickens_owned <= 0:
            return await interaction.followup.send(
                f"❌ You need at least one {CHICKEN_EMOJI} Chicken to participate in a cockfight! Buy one from `/shop`.",
                ephemeral=True
            )

        # --- Cockfight Simulation ---
        # Initial message to start the fight
        await interaction.followup.send(
            f"{interaction.user.mention}'s {CHICKEN_EMOJI} Chicken enters the arena, betting ₱{bet_amount:,}! {FIGHT_EMOJI}\n"
            f"The fight is on... (Result in 3 seconds)"
        )

        # Simulate fight delay
        await asyncio.sleep(3) # A 3-second delay for suspense

        # Determine outcome (50/50 chance for now, you can adjust this logic later)
        is_win = random.choice([True, False]) # True for Win, False for Lose

        if is_win:
            # Player wins: Increase balance, chickens_owned remains the same
            amount_change_balance = bet_amount
            # No change to chickens on win
            
            new_balance = current_balance + amount_change_balance
            new_chickens_owned = chickens_owned # Chickens don't change on a win

            # Update database
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": amount_change_balance}},
                upsert=True
            )
            
            # Send win message
            await interaction.followup.send(
                f"🎉 {interaction.user.mention}'s {CHICKEN_EMOJI} Chicken fought bravely and WON ₱{bet_amount:,}!\n"
                f"{WIN_EMOJI} Your new balance is ₱{new_balance:,}.\n"
                f"You still have {new_chickens_owned} {CHICKEN_EMOJI} Chicken(s)."
            )
        else:
            # Player loses: Decrease balance, lose one chicken
            amount_change_balance = -bet_amount
            amount_change_chickens = -1 # Lose one chicken

            new_balance = current_balance + amount_change_balance
            new_chickens_owned = chickens_owned + amount_change_chickens # Decrement by 1

            # Update database
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": amount_change_balance, "chickens_owned": amount_change_chickens}},
                upsert=True
            )
            
            # Send loss message
            await interaction.followup.send(
                f"💔 {interaction.user.mention}'s {CHICKEN_EMOJI} Chicken put up a good fight but sadly LOST ₱{bet_amount:,} and one of its own!\n"
                f"{LOSE_EMOJI} Your new balance is ₱{new_balance:,}.\n"
                f"You now have {new_chickens_owned} {CHICKEN_EMOJI} Chicken(s) left."
            )

    def cog_unload(self):
        self.client.close()
        print("Cockfight MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Cockfight(bot))