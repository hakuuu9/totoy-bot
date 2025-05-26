import discord
from discord import app_commands
from discord.ext import commands
import random

class CoinFlip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flip a coin and see if you win!")
    @app_commands.describe(choice="Choose head or tail")
    async def coinflip(self, interaction: discord.Interaction, choice: str):
        choice = choice.lower()
        if choice not in ["head", "tail"]:
            return await interaction.response.send_message("❌ Please choose either `head` or `tail`.", ephemeral=True)

        flipping_emoji = "<a:flipping:1376592368836415598>"
        head_emoji = "<:head:1376592499426201650>"
        tail_emoji = "<:tail:1376592674186068200>"

        # Send initial flip message
        await interaction.response.send_message(f"You chose **{choice}** {flipping_emoji}")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=2))

        result = random.choice(["head", "tail"])
        result_emoji = head_emoji if result == "head" else tail_emoji

        win = "✅ You win!" if result == choice else "❌ You lose!"
        await interaction.followup.send(
            f"The coin landed on **{result}** {result_emoji}\n{win}"
        )

async def setup(bot):
    await bot.add_cog(CoinFlip(bot))
