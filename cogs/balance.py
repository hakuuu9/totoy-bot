import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL

class Balance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users

    @commands.command(name='balance')
    async def balance_text(self, ctx):
        await self.show_balance(ctx.author, ctx)

    @app_commands.command(name='balance', description='Check your coin balance')
    async def balance_slash(self, interaction: discord.Interaction):
        await self.show_balance(interaction.user, interaction)

    async def show_balance(self, user, ctx_or_interaction):
        user_data = self.db.find_one({'_id': str(user.id)})
        balance = user_data['balance'] if user_data and 'balance' in user_data else 0
        emoji = "<:1916pepecoin:1376564847088504872>"
        message = f"Your current balance is ₱{balance} {emoji}"

        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(Balance(bot))
