import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL
import random
import time

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = MongoClient(MONGO_URL).hxhbot.users

        self.emoji = "<:arcadiacoin:1378656679704395796>"
        self.messages = [
            # Tagalog
            "Totoy, nagbanat ng buto pero ang sweldo ₱{salary} {emoji} para na rin sa mga pang hugas ng luha mo.\n\n"
            "Bagong balance mo: ₱{balance} {emoji}\nLaban lang, kapit lang, pre!",
            "Grabe ang sipag mo, pre! ₱{salary} {emoji} ang pasalubong mo ngayon.\nBalance mo ay ₱{balance} {emoji} na!",
            "Ayos 'to, ₱{salary} {emoji} ang pasok mo! Keep it up, kapatid.\nNgayon ₱{balance} {emoji} na ang pera mo.",

            # English
            "You worked hard and earned ₱{salary} {emoji}!\nYour new balance is ₱{balance} {emoji}. Keep grinding!",
            "Nice hustle! ₱{salary} {emoji} added to your wallet.\nTotal balance: ₱{balance} {emoji}. Don't stop now!",
            "Your effort paid off: ₱{salary} {emoji} earned.\nBalance now: ₱{balance} {emoji}. Keep up the good work!",

            # Formal
            "Congratulations! You have received a salary of ₱{salary} {emoji}.\nYour updated balance is ₱{balance} {emoji}.",
            "Your work has been compensated with ₱{salary} {emoji}.\nCurrent balance: ₱{balance} {emoji}.",
            "You earned ₱{salary} {emoji} for your efforts today.\nNew balance: ₱{balance} {emoji}."
        ]

    def is_on_cooldown(self, user_id):
        user_data = self.db.find_one({'_id': str(user_id)})
        now = time.time()

        if not user_data or 'next_work_time' not in user_data:
            return False, 0

        next_time = user_data['next_work_time']
        remaining = next_time - now

        if remaining > 0:
            return True, round(remaining)
        return False, 0

    def set_new_cooldown(self, user_id):
        # Random cooldown: 3 minutes to 2 hours (180–7200 seconds)
        cooldown_duration = random.randint(180, 7200)
        next_time = time.time() + cooldown_duration
        self.db.update_one(
            {'_id': str(user_id)},
            {'$set': {'next_work_time': next_time}},
            upsert=True
        )
        return cooldown_duration

    @commands.command(name='work')
    async def work_text(self, ctx):
        is_cooldown, remaining = self.is_on_cooldown(ctx.author.id)
        if is_cooldown:
            await ctx.send(f"You're tired! You can work again in {remaining} seconds.")
            return
        await self.handle_work(ctx.author, ctx)

    @app_commands.command(name='work', description='Work to earn a salary (cooldown: 3m–2h, random)')
    async def work_slash(self, interaction: discord.Interaction):
        is_cooldown, remaining = self.is_on_cooldown(interaction.user.id)
        if is_cooldown:
            await interaction.response.send_message(
                f"You're tired! You can work again in {remaining} seconds.", ephemeral=True
            )
            return

        await interaction.response.defer()  # prevent the timeout
        await self.handle_work(interaction.user, interaction)

    async def handle_work(self, user, ctx_or_interaction):
        salary = random.randint(1, 200)

        user_data = self.db.find_one({'_id': str(user.id)})
        balance = user_data['balance'] if user_data and 'balance' in user_data else 0
        new_balance = balance + salary

        self.db.update_one({'_id': str(user.id)}, {
            '$set': {
                'balance': new_balance
            }
        }, upsert=True)

        # Set random cooldown
        cooldown_duration = self.set_new_cooldown(user.id)

        # Choose a random message
        message_template = random.choice(self.messages)
        message = message_template.format(salary=salary, balance=new_balance, emoji=self.emoji)
        message += f"\n\nNext work available in {cooldown_duration // 60} minutes."

        await self.send_response(ctx_or_interaction, message)

    async def send_response(self, ctx_or_interaction, message):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(message)
        else:
            await ctx_or_interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(Work(bot))