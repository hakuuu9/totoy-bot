import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.daily  # Adjust if your coin data is elsewhere

    @app_commands.command(name="leaderboard", description="View the top 20 richest members")
    async def leaderboard(self, interaction: discord.Interaction):
        top_users = list(self.db.find().sort("coins", -1).limit(20))

        if not top_users:
            return await interaction.response.send_message("❌ No one has coins yet.", ephemeral=True)

        description = ""
        for index, user in enumerate(top_users, start=1):
            member = interaction.guild.get_member(int(user["_id"]))
            name = member.display_name if member else f"<@{user['_id']}>"
            coins = user.get("coins", 0)
            description += f"**{index}.** {name} — ₱{coins}\n"

        embed = discord.Embed(
            title="<a:lb:1376576752414883953> Kinsay Sikat sa Barya?",
            description=description,
            color=discord.Color.from_str("#000000")
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
