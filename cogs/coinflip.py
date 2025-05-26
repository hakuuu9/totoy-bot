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
        self.db = MongoClient(MONGO_URL).hxhbot.daily

        # Emoji IDs
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

        if amount <= 0:
            return await interaction.response.send_message("❌ Bet amount must be more than zero.")

        user_data = self.db.find_one({"_id": user_id})
        balance = user_data.get("balance", 0) if user_data else 0

        if balance < amount:
            return await interaction.response.send_message(f"❌ You only have ₱{balance}.")

        # Subtract the bet amount
        self.db.update_one({"_id": user_id}, {"$inc": {"balance": -amount}}, upsert=True)

        # Initial flipping message
        await interaction.response.send_message(
            f"You chose **{side}** {self.flip_emoji}\nFlipping the coin..."
        )

        await asyncio.sleep(2)

        result = random.choice(["head", "tail"])
        result_emoji = self.head_emoji if result == "head" else self.tail_emoji

        if side == result:
            reward = amount * 2
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": reward}})
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n🎉 You won ₱{reward}!"
            )
        else:
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n😞 You lost ₱{amount}."
            )

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
