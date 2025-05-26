import discord
from discord import app_commands
from discord.ext import commands
import random
from pymongo import MongoClient
from config import MONGO_URL

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users  # Your users collection

    @app_commands.command(name="coinflip", description="Bet coins on a coin flip (head or tail)")
    @app_commands.describe(
        choice="Choose head or tail",
        amount="Amount of coins to bet"
    )
    async def coinflip(self, interaction: discord.Interaction, choice: str, amount: int):
        choice = choice.lower()
        if choice not in ["head", "tail"]:
            return await interaction.response.send_message("❌ Please choose either `head` or `tail`.", ephemeral=True)

        if amount <= 0:
            return await interaction.response.send_message("❌ Bet amount must be greater than zero.", ephemeral=True)

        user_id = str(interaction.user.id)
        user_data = self.db.find_one({"_id": user_id})

        if not user_data or user_data.get("coins", 0) < amount:
            return await interaction.response.send_message("❌ You don't have enough coins to bet that amount.", ephemeral=True)

        flipping_emoji = "<a:flipping:1376592368836415598>"
        head_emoji = "<:head:1376592499426201650>"
        tail_emoji = "<:tail:1376592674186068200>"

        # Send initial flip message
        await interaction.response.send_message(f"You chose **{choice}** {flipping_emoji}")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=2))

        result = random.choice(["head", "tail"])
        result_emoji = head_emoji if result == "head" else tail_emoji

        if result == choice:
            # Win: double the bet amount added
            new_balance = user_data.get("coins", 0) + amount
            self.db.update_one({"_id": user_id}, {"$inc": {"coins": amount}})
            msg = f"🎉 The coin landed on **{result}** {result_emoji}\n✅ You won {amount} coins! Your new balance is ₱{new_balance}."
        else:
            # Lose: bet amount deducted
            new_balance = user_data.get("coins", 0) - amount
            self.db.update_one({"_id": user_id}, {"$inc": {"coins": -amount}})
            msg = f"😞 The coin landed on **{result}** {result_emoji}\n❌ You lost {amount} coins. Your new balance is ₱{new_balance}."

        await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
