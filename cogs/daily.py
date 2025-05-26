import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from pymongo import MongoClient
from config import MONGO_URL

class Daily(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users  # Make sure this points to your 'users' collection

    @commands.command(name='daily')
    async def daily_text(self, ctx):
        await self.handle_daily(ctx.author, ctx)

    @app_commands.command(name='daily', description='Claim your daily reward (₱500 every 24h)')
    async def daily_slash(self, interaction: discord.Interaction):
        await self.handle_daily(interaction.user, interaction)

    async def handle_daily(self, user, ctx_or_interaction):
        now = datetime.utcnow()
        user_data = self.db.find_one({'_id': str(user.id)})

        amount = 500
        emoji = "<:1916pepecoin:1376564847088504872>"

        if user_data and 'last_claim' in user_data:
            last_claim = user_data['last_claim']
            next_claim_time = last_claim + timedelta(days=1)
            if now < next_claim_time:
                remaining = next_claim_time - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                message = f"❌ You've already claimed your daily. Try again in {hours}h {minutes}m."
                return await self.send_response(ctx_or_interaction, message)

        new_balance = (user_data['balance'] if user_data else 0) + amount

        self.db.update_one(
            {'_id': str(user.id)},
            {'$set': {'last_claim': now, 'balance': new_balance}},
            upsert=True
        )

        message = f"You received **__₱ {amount} {emoji}__**\n You Beggar Daily Reward Claimed!"
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
    await bot.add_cog(Daily(bot))
