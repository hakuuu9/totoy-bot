import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from pymongo import MongoClient
from config import MONGO_URL # Assuming config.py is in the same directory

# Define your custom animated color emojis
GREEN_EMOJI = "<a:greeng:1376794387521998932>"
YELLOW_EMOJI = "<a:yellowg:1376794344673116301>"
PINK_EMOJI = "<a:pinkg:1376794288012263444>"

# List of available colors and their corresponding emojis
COLORS = {
    "green": GREEN_EMOJI,
    "yellow": YELLOW_EMOJI,
    "pink": PINK_EMOJI,
}

# The colors that will be 'rolled' by the dice
ROLLABLE_COLORS = list(COLORS.keys())

class ColorGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the same 'users' collection

    @app_commands.command(name="colorgame", description="Bet on colors in a perya-style game!")
    @app_commands.describe(
        bet_amount="The amount of ₱ to bet on EACH chosen color.",
        color1="Your first color choice.",
        color2="Your second color choice (optional).",
        color3="Your third color choice (optional)."
    )
    @app_commands.choices(
        color1=[
            app_commands.Choice(name="Green", value="green"),
            app_commands.Choice(name="Yellow", value="yellow"),
            app_commands.Choice(name="Pink", value="pink"),
        ],
        color2=[
            app_commands.Choice(name="Green", value="green"),
            app_commands.Choice(name="Yellow", value="yellow"),
            app_commands.Choice(name="Pink", value="pink"),
        ],
        color3=[
            app_commands.Choice(name="Green", value="green"),
            app_commands.Choice(name="Yellow", value="yellow"),
            app_commands.Choice(name="Pink", value="pink"),
        ],
    )
    async def colorgame(self, interaction: discord.Interaction, bet_amount: int, color1: str, color2: str = None, color3: str = None):
        user_id = str(interaction.user.id)
        chosen_colors = [color1]
        if color2:
            chosen_colors.append(color2)
        if color3:
            chosen_colors.append(color3)
        
        # Remove duplicates from chosen_colors, betting on the same color multiple times doesn't make sense
        chosen_colors = list(dict.fromkeys(chosen_colors)) 

        # Defer the response immediately
        await interaction.response.defer(ephemeral=False)

        user_data = self.db.find_one({"_id": user_id})
        current_balance = int(user_data.get("balance", 0)) if user_data else 0

        total_bet_cost = bet_amount * len(chosen_colors)

        # --- Input Validation ---
        if bet_amount <= 0:
            return await interaction.followup.send("❌ You must bet a positive amount.", ephemeral=True)
        
        if total_bet_cost > current_balance:
            return await interaction.followup.send(
                f"❌ You don't have enough money! Your total bet is ₱{total_bet_cost:,} but you only have ₱{current_balance:,}.",
                ephemeral=True
            )

        # Display chosen colors
        chosen_color_emojis = [COLORS[c] for c in chosen_colors]
        await interaction.followup.send(
            f"{interaction.user.mention} is betting ₱{bet_amount:,} on {', '.join(chosen_color_emojis)}!\n"
            f"Total bet: ₱{total_bet_cost:,}. Rolling the colors! {random.choice(list(COLORS.values()))} {random.choice(list(COLORS.values()))} {random.choice(list(COLORS.values()))}"
        )

        # --- Rolling Animation ---
        roll_message = await interaction.channel.send("Rolling... 🎲")
        
        for _ in range(5): # Roll 5 times for animation effect
            rolled_emojis = [random.choice(list(COLORS.values())) for _ in range(3)]
            await roll_message.edit(content=f"Rolling... {rolled_emojis[0]} {rolled_emojis[1]} {rolled_emojis[2]}")
            await asyncio.sleep(0.7) # Adjust speed of roll animation

        # --- Determine Outcome ---
        final_roll_colors = [random.choice(ROLLABLE_COLORS) for _ in range(3)]
        final_roll_emojis = [COLORS[c] for c in final_roll_colors]

        winnings = 0
        losses = 0
        
        # Track which chosen colors appeared and how many times
        results_summary = {} 

        # Calculate winnings/losses for each chosen color
        for chosen_color in chosen_colors:
            count = final_roll_colors.count(chosen_color)
            if count > 0:
                winnings += bet_amount * count # Win 1x, 2x, or 3x the bet for that color
                results_summary[chosen_color] = f"Won ₱{bet_amount * count:,} ({count}x)"
            else:
                losses += bet_amount # Lose the bet for that specific color
                results_summary[chosen_color] = "Lost ₱" + str(bet_amount)

        # Calculate total win/loss
        net_change = winnings - total_bet_cost
        new_balance = current_balance + net_change

        # --- Update Balance ---
        self.db.update_one(
            {"_id": user_id},
            {"$inc": {"balance": net_change}},
            upsert=True
        )

        # --- Send Final Result ---
        result_embed = discord.Embed(
            title="🎲 Color Game Results! 🎲",
            description=f"The colors rolled: {final_roll_emojis[0]} {final_roll_emojis[1]} {final_roll_emojis[2]}\n\n",
            color=discord.Color.from_rgb(255, 165, 0) # Orange color for result
        )

        # Add details for each chosen color
        for color, result_str in results_summary.items():
            result_embed.add_field(name=f"{COLORS[color]} {color.capitalize()}", value=f"• {result_str}", inline=True)

        if net_change > 0:
            result_embed.description += f"**🎉 You won a total of ₱{net_change:,}!**"
            result_embed.color = discord.Color.green()
        elif net_change < 0:
            result_embed.description += f"**💔 You lost a total of ₱{abs(net_change):,}!**"
            result_embed.color = discord.Color.red()
        else:
            result_embed.description += f"**⚖️ It's a draw! Your net change is ₱0.**"
            result_embed.color = discord.Color.gold()

        result_embed.set_footer(text=f"Your new balance: ₱{new_balance:,}.")

        await roll_message.delete() # Delete the rolling message
        await interaction.followup.send(embed=result_embed)


    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("ColorGame MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(ColorGame(bot))