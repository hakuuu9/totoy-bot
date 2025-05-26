import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from config import MONGO_URL

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.daily  # Your user collection

        # Your emojis from portal
        self.flip_emoji = "<a:flipping:1376592368836415598>"
        self.head_emoji = "<:head:1376592499426201650>"
        self.tail_emoji = "<:tail:1376592674186068200>"

    @app_commands.command(name="coinflip", description="Flip a coin and bet coins")
    @app_commands.describe(side="Choose head or tail", amount="Amount of coins to bet")
    async def coinflip(self, interaction: discord.Interaction, side: str, amount: int):
        side = side.lower()
        user_id = str(interaction.user.id)

        if side not in ["head", "tail"]:
            return await interaction.response.send_message("❌ Please choose 'head' or 'tail'.")

        # Fetch user data
        user_data = self.db.find_one({"_id": user_id})

        if not user_data or user_data.get("balance", 0) < amount:
            return await interaction.response.send_message("❌ You don't have enough coins to bet that amount.")

        if amount <= 0:
            return await interaction.response.send_message("❌ Bet amount must be greater than zero.")

        # Deduct bet upfront
        self.db.update_one({"_id": user_id}, {"$inc": {"balance": -amount}})

        # Send initial flip message
        await interaction.response.send_message(f"You chose **{side}** {self.flip_emoji}\nFlipping the coin...")

        # Wait 2 seconds to simulate flip
        await asyncio.sleep(2)

        # Determine result
        result = random.choice(["head", "tail"])
        result_emoji = self.head_emoji if result == "head" else self.tail_emoji

        if side == result:
            reward = amount * 2
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": reward}})  # Add winnings

            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n You won ₱{reward} coins!"
            )
        else:
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n You lost ₱{amount} coins."
            )

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
