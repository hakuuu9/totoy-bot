import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from config import MONGO_URL # Assuming config.py is in the same directory

# Define your custom animated spider emojis
SPIDER_RIGHT_EMOJI = "<:spider11:1376855645931704450>"
SPIDER_LEFT_EMOJI = "<:spider22:1376855660331012096>"
FIGHT_EMOJI = "⚔️" # General fight emoji
CLASH_EMOJI = "💥" # For impact effect

class SpiderDerby(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the 'users' collection

    @app_commands.command(name="spiderderby", description="Bet your ₱ on a thrilling spider derby!")
    @app_commands.describe(
        bet_amount="The amount of ₱ you want to bet.",
        spider_choice="Choose your champion spider!"
    )
    @app_commands.choices(
        spider_choice=[
            app_commands.Choice(name="Right Spider", value="right"),
            app_commands.Choice(name="Left Spider", value="left"),
        ]
    )
    async def spiderderby(self, interaction: discord.Interaction, bet_amount: int, spider_choice: str):
        user_id = str(interaction.user.id)

        # Defer the response immediately to prevent timeout
        await interaction.response.defer(ephemeral=False)

        user_data = self.db.find_one({"_id": user_id})
        current_balance = int(user_data.get("balance", 0)) if user_data else 0

        # --- Input Validation ---
        if bet_amount <= 0:
            return await interaction.followup.send("❌ You must bet a positive amount.", ephemeral=True)

        if current_balance < bet_amount:
            return await interaction.followup.send(
                f"❌ You don't have enough money! You have ₱{current_balance:,} but tried to bet ₱{bet_amount:,}.",
                ephemeral=True
            )

        # Map choice string to emoji
        chosen_spider_emoji = SPIDER_RIGHT_EMOJI if spider_choice == "right" else SPIDER_LEFT_EMOJI
        chosen_spider_name = "Going Right Spider" if spider_choice == "right" else "Going Left Spider"

        # --- Spider Derby Introduction ---
        await interaction.followup.send(
            f"{interaction.user.mention} placed a bet of ₱{bet_amount:,} on the **{chosen_spider_name}** {chosen_spider_emoji}!\n"
            f"The spiders are ready! {SPIDER_RIGHT_EMOJI} {FIGHT_EMOJI} {SPIDER_LEFT_EMOJI}"
        )

        # --- NEW: Battle Animation ---
        battle_message = await interaction.channel.send("The spiders are battling fiercely... 🕷️💨🕸️")
        
        animation_frames = [
            f"{SPIDER_RIGHT_EMOJI}  {FIGHT_EMOJI}  {SPIDER_LEFT_EMOJI}",
            f"  {SPIDER_RIGHT_EMOJI}{FIGHT_EMOJI}{SPIDER_LEFT_EMOJI}  ",
            f"{SPIDER_RIGHT_EMOJI}{CLASH_EMOJI}{SPIDER_LEFT_EMOJI}",
            f" {SPIDER_LEFT_EMOJI} {FIGHT_EMOJI} {SPIDER_RIGHT_EMOJI}",
            f"{SPIDER_LEFT_EMOJI}   {FIGHT_EMOJI}   {SPIDER_RIGHT_EMOJI} {CLASH_EMOJI}",
            f"{SPIDER_RIGHT_EMOJI} {FIGHT_EMOJI} {SPIDER_LEFT_EMOJI} 💥",
            f"🕷️⚔️🕸️", # A more condensed clash
        ]

        for _ in range(7): # Loop through 7 animation steps for about 3.5 seconds of animation
            frame = random.choice(animation_frames) # Pick a random frame each time
            await battle_message.edit(content=f"The spiders are battling fiercely... {frame}")
            await asyncio.sleep(0.5) # Control the speed of each frame

        await battle_message.delete() # Delete the animation message before revealing the result
        # --- END NEW BATTLE ANIMATION ---

        # --- Determine Outcome (existing logic) ---
        winning_spider_value = random.choice(["right", "left"])
        
        # Map winning value to actual emoji and name
        winning_spider_emoji = SPIDER_RIGHT_EMOJI if winning_spider_value == "right" else SPIDER_LEFT_EMOJI
        winning_spider_name = "Right Spider" if winning_spider_value == "right" else "Left Spider"

        if winning_spider_value == spider_choice:
            # Player wins
            net_change = bet_amount # Player wins their bet back, plus an equal amount (total 2x original bet)
            new_balance = current_balance + net_change
            
            # Update database
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": net_change}},
                upsert=True
            )
            
            # Send win message
            await interaction.followup.send(
                f"🎉 **VICTORY!** The **{winning_spider_name}** {winning_spider_emoji} emerged victorious!\n"
                f"{interaction.user.mention} won ₱{net_change:,}!\n"
                f"Your new balance is ₱{new_balance:,}."
            )
        else:
            # Player loses
            net_change = -bet_amount
            new_balance = current_balance + net_change

            # Update database
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": net_change}},
                upsert=True
            )
            
            # Send loss message
            await interaction.followup.send(
                f"💔 **DEFEAT!** The **{winning_spider_name}** {winning_spider_emoji} reigned supreme.\n"
                f"{interaction.user.mention} lost ₱{bet_amount:,}.\n"
                f"Your new balance is ₱{new_balance:,}."
            )

    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("SpiderDerby MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(SpiderDerby(bot))