import discord
from discord.ext import commands
from discord import app_commands
import random
from pymongo import MongoClient
from config import MONGO_URL

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users  # Adjust to your collection

    @app_commands.command(name="coinflip", description="Flip a coin and bet your ₱")
    @app_commands.describe(choice="Choose head or tail", amount="Amount to bet")
    async def coinflip(self, interaction: discord.Interaction, choice: str, amount: int):
        choice = choice.lower()
        if choice not in ["head", "tail"]:
            return await interaction.response.send_message("❌ Choose either `head` or `tail`.", ephemeral=True)

        user_id = str(interaction.user.id)
        user_data = self.db.find_one({"_id": user_id})
        balance = int(user_data.get("balance", 0)) if user_data else 0

        if amount <= 0:
            return await interaction.response.send_message("❌ Bet amount must be greater than ₱0.", ephemeral=True)

        if balance < amount:
            return await interaction.response.send_message(f"❌ You only have ₱{balance}.", ephemeral=True)

        await interaction.response.send_message(f"You chose **{choice}** <a:flipping:1376592368836415598>\nFlipping the coin...")

        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=2))  # Delay 2s
        result = random.choice(["head", "tail"])
        result_emoji = "<:head:1376592499426201650>" if result == "head" else "<:tail:1376592674186068200>"

        if choice == result:
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": amount}})
            await interaction.followup.send(f"The coin landed on **{result}** {result_emoji}\n✅ You won ₱{amount}!")
        else:
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": -amount}})
            await interaction.followup.send(f"The coin landed on **{result}** {result_emoji}\n❌ You lost ₱{amount}.")

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
