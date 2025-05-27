import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL
import random
from datetime import datetime, timedelta

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users  # Collection for user balances
        self.cooldowns = {}  # To track cooldowns by user ID

    @commands.command(name='work')
    @commands.cooldown(1, 10, commands.BucketType.user)  # 1 use every 10 sec per user
    async def work_text(self, ctx):
        await self.handle_work(ctx.author, ctx)

    @app_commands.command(name='work', description='Work to earn a small salary (10s cooldown)')
    async def work_slash(self, interaction: discord.Interaction):
        await self.handle_work(interaction.user, interaction)

    async def handle_work(self, user, ctx_or_interaction):
        # Random salary between 1 and 20
        salary = random.randint(1, 20)

        # Fetch or create user balance
        user_data = self.db.find_one({'_id': str(user.id)})
        if user_data and 'balance' in user_data:
            balance = user_data['balance']
        else:
            balance = 0

        new_balance = balance + salary

        # Update balance in DB
        self.db.update_one({'_id': str(user.id)}, {'$set': {'balance': new_balance}}, upsert=True)

        emoji = "<a:9470coin:1376564873332391966>"
        message = (
            f"Totoy, nagbanat ng buto pero ang sweldo ₱{salary} {emoji} para na rin sa mga pang hugas ng luha mo.\n\n"
            f"Bagong balance mo: ₱{new_balance} {emoji} laban lang, kapit lang, pre!"

        )

        await self.send_response(ctx_or_interaction, message)

    async def send_response(self, ctx_or_interaction, message):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(message)
        else:
            if ctx_or_interaction.response.is_done():
                await ctx_or_interaction.followup.send(message)
            else:
                await ctx_or_interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(Work(bot))
