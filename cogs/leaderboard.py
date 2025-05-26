import discord
from discord.ext import commands
from pymongo import MongoClient
from config import MONGO_URL

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.daily  # Assuming same collection storing coins

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        lb_gif = "<a:lb:1376576752414883953>"

        # Get top 10 users sorted by coins descending
        top_users = self.db.find().sort("coins", -1).limit(10)

        if top_users.count() == 0:
            await ctx.send("Walay data sa leaderboard.")
            return

        description = ""
        rank = 1
        for user in top_users:
            user_id = int(user['_id'])
            coins = user.get('coins', 0)
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User ID {user_id}"
            description += f"**{rank}.** {name} — ₱{coins}\n"
            rank += 1

        embed = discord.Embed(
            title=f"{lb_gif} Kinsay Sikat sa Barya?",
            description=description,
            color=discord.Color.from_rgb(0, 0, 0)  # Black
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
