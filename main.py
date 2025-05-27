import discord
from discord.ext import commands
from keep_alive import keep_alive
from config import BOT_TOKEN
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True  # Needed for chat commands

bot = commands.Bot(command_prefix="sin ", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'Error syncing slash commands: {e}')

async def main():
    # Load all cogs from /cogs
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
    
    # Start keep-alive server (if needed)
    keep_alive()
    
    # Run the bot
    await bot.start(BOT_TOKEN)

# Run the async main() function
asyncio.run(main())
