import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import random
from config import MONGO_URL

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users  # Your users collection

    @app_commands.command(name="coinflip", description="Bet coins on a coin flip. Choose head or tail.")
    @app_commands.describe(
        side="Choose head or tail",
        amount="Amount of coins to bet"
    )
    async def coinflip(self, interaction: discord.Interaction, side: str, amount: int):
        side = side.lower()
        if side not in ["head", "tail"]:
            await interaction.response.send_message("❌ You must choose `head` or `tail`.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.response.send_message("❌ Bet amount must be greater than zero.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        user_data = self.db.find_one({"_id": user_id})

        if not user_data or user_data.get("balance", 0) < amount:
            await interaction.response.send_message("❌ You don't have enough coins to bet that amount.", ephemeral=True)
            return

        # Deduct bet amount
        self.db.update_one({"_id": user_id}, {"$inc": {"balance": -amount}})

        # Emojis
        flip_emoji = "<a:flipping:1376592368836415598>"
        head_emoji = "<:head:1376592499426201650>"
        tail_emoji = "<:tail:1376592674186068200>"

        await interaction.response.send_message(
            f"You chose **{side}** {flip_emoji}\nFlipping the coin..."
        )

        # Wait 2 seconds to simulate flipping
        await discord.utils.sleep_until(interaction.created_at + discord.utils.timedelta(seconds=2))

        result = random.choice(["head", "tail"])
        result_emoji = head_emoji if result == "head" else tail_emoji

        if side == result:
            reward = amount * 2
            self.db.update_one({"_id": user_id}, {"$inc": {"balance": reward}})

            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n You won ₱{reward} coins!"
            )
        else:
            await interaction.followup.send(
                f"The coin landed on **{result}** {result_emoji}\n You lost ₱{amount} coins."
            )

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
