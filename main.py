import os
import asyncio
import threading
from flask import Flask
import discord
from discord.ext import commands
import asyncio

from config import BOT_TOKEN

# Create Flask app for keep-alive endpoint
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run_web():
    # Render provides PORT as an environment variable
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def start_webserver():
    # Run the Flask app in a new thread so that it doesn't block the bot
    web_thread = threading.Thread(target=run_web)
    web_thread.start()

# Set up Discord bot
intents = discord.Intents.default()
intents.message_content = True  # Enable if needed for chat commands
bot = commands.Bot(command_prefix="hxh ", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    # Start the web server first
    start_webserver()
    # Load cogs then start the bot
    await load_cogs()
    await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
