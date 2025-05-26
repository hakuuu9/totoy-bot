import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.daily  # Make sure your coins are stored in .daily

    @app_commands.command(name="leaderboard", description="View the top 20 richest members")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()  # To prevent timeout

        top_users = list(self.db.find().sort("coins", -1).limit(20))
        if not top_users:
            return await interaction.followup.send("❌ Walay kwartang tao pa.")

        embed = discord.Embed(
            title="<a:lb:1376576752414883953> Kinsay Sikat sa Barya?",
            description="",
            color=discord.Color.from_str("#000000")
        )

        for index, user in enumerate(top_users, start=1):
            user_id = int(user["_id"])
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            coins = user.get("coins", 0)
            embed.description += f"**{index}.** {name} — ₱{coins}\n"

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
