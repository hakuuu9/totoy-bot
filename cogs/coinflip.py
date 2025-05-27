import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from config import MONGO_URL # Assuming config.py is in the same directory

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Connect to MongoDB
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users  # Adjust to your database and collection name

    @app_commands.command(name="coinflip", description="Flip a coin and bet your ₱")
    @app_commands.describe(choice="Choose head or tail", amount="Amount to bet")
    async def coinflip(self, interaction: discord.Interaction, choice: str, amount: int):
        choice = choice.lower()
        if choice not in ["head", "tail"]:
            return await interaction.response.send_message("❌ Choose either `head` or `tail`.", ephemeral=True)

        user_id = str(interaction.user.id)

        # Defer the response immediately as the command involves database interaction and a delay
        await interaction.response.defer()

        user_data = self.db.find_one({"_id": user_id})
        # Initialize balance to 0 if user_data is None or balance key is missing
        balance = int(user_data.get("balance", 0)) if user_data else 0

        if amount <= 0:
            return await interaction.followup.send("❌ Bet amount must be greater than ₱0.", ephemeral=True)

        if balance < amount:
            return await interaction.followup.send(f"❌ You only have ₱{balance}.", ephemeral=True)

        # Inform the user that the coin is flipping
        await interaction.followup.send(f"You chose **{choice.capitalize()}** <a:flipping:1376592368836415598>\nFlipping the coin...")

        # Delay for 2 seconds
        await asyncio.sleep(2)  

        result = random.choice(["head", "tail"])
        result_emoji = "<:head:1376592499426201650>" if result == "head" else "<:tail:1376592674186068200>"

        # Define your custom win/loss emojis
        win_emoji = "<:win_cf:1376735656042299483>"
        lose_emoji = "<:lose_cf:1376735674132332574>"

        if choice == result:
            # Update balance: increment by amount, upsert=True to create document if it doesn't exist
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": amount}}, upsert=True)
            new_balance = balance + amount
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n"
                f"{win_emoji} You won ₱{amount}!\n" # Using custom win emoji
                f"Your new balance is ₱{new_balance}."
            )
        else:
            # Update balance: decrement by amount, upsert=True to create document if it doesn't exist
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": -amount}}, upsert=True)
            new_balance = balance - amount
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n"
                f"{lose_emoji} You lost ₱{amount}.\n" # Using custom lose emoji
                f"Your new balance is ₱{new_balance}."
            )

    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("CoinFlip MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))