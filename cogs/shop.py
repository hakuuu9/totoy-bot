import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL # Assuming config.py is in the same directory

# Define your custom chicken emoji
CHICKEN_EMOJI = "<:chickenshop:1376780896149176420>"
CHICKEN_COST = 10

# New: Define Anti-Rob item details with your custom emoji
ANTI_ROB_EMOJI = "<:antirob:1376801124656349214>" # Your custom anti-rob emoji
ANTI_ROB_COST = 1000

class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Connect to the same 'users' collection

    @app_commands.command(name="shop", description="View items available for purchase.")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Totoy's Chicken Shop",
            description=(
                f"Welcome to the finest chicken market in town! "
                f"Spend your hard-earned ₱ to get your hands on some feathery friends.\n\n"
                f"**Available Items:**\n"
                f"• {CHICKEN_EMOJI} **Chicken** - ₱{CHICKEN_COST}\n"
                f"  *(Use `/buy chicken <amount>` to purchase)*\n\n"
                f"• {ANTI_ROB_EMOJI} **Anti-Rob Shield** - ₱{ANTI_ROB_COST}\n"
                f"  *(Use `/buy anti-rob <amount>` to purchase. Requires `/use anti-rob` later!)*"
            ),
            color=discord.Color.from_rgb(255, 223, 0) # Gold-like color for a shop
        )
        embed.set_thumbnail(url="https://i.imgur.com/example_chicken_shop_icon.png") # Replace with a relevant image URL
        embed.set_footer(text="🐔 Get ready for some cockfighting!")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy items from the shop.")
    @app_commands.describe(item="The item you want to buy.", amount="The quantity to buy.")
    async def buy(self, interaction: discord.Interaction, item: str, amount: int):
        user_id = str(interaction.user.id)
        item = item.lower() # Convert item name to lowercase for consistent checking

        # Defer the response as we'll be interacting with the database
        await interaction.response.defer(ephemeral=False)

        user_data = self.db.find_one({"_id": user_id})
        current_balance = int(user_data.get("balance", 0)) if user_data else 0
        chickens_owned = int(user_data.get("chickens_owned", 0)) if user_data else 0
        # Get current anti-rob items owned
        anti_rob_items_owned = int(user_data.get("anti_rob_items", 0)) if user_data else 0

        if amount <= 0:
            return await interaction.followup.send("❌ You need to buy at least 1 item.", ephemeral=True)

        if item == "chicken":
            total_cost = CHICKEN_COST * amount
            if current_balance < total_cost:
                return await interaction.followup.send(
                    f"❌ You don't have enough money! You need ₱{total_cost:,} but only have ₱{current_balance:,}.", 
                    ephemeral=True
                )

            # Update user's balance and chickens_owned
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": -total_cost, "chickens_owned": amount}},
                upsert=True
            )

            new_balance = current_balance - total_cost
            new_chickens_owned = chickens_owned + amount

            await interaction.followup.send(
                f"✅ You successfully bought {amount} {CHICKEN_EMOJI} **Chicken(s)** for ₱{total_cost:,}!\n"
                f"Your new balance is ₱{new_balance:,}.\n"
                f"You now own {new_chickens_owned} {CHICKEN_EMOJI} Chicken(s)."
            )
        elif item == "anti-rob": # Logic for Anti-Rob item
            total_cost = ANTI_ROB_COST * amount
            if current_balance < total_cost:
                return await interaction.followup.send(
                    f"❌ You don't have enough money! You need ₱{total_cost:,} but only have ₱{current_balance:,}.", 
                    ephemeral=True
                )
            
            # Update user's balance and anti_rob_items_owned
            self.db.update_one(
                {"_id": user_id},
                {"$inc": {"balance": -total_cost, "anti_rob_items": amount}},
                upsert=True
            )

            new_balance = current_balance - total_cost
            new_anti_rob_items_owned = anti_rob_items_owned + amount

            await interaction.followup.send(
                f"✅ You successfully bought {amount} {ANTI_ROB_EMOJI} **Anti-Rob Shield(s)** for ₱{total_cost:,}!\n"
                f"Your new balance is ₱{new_balance:,}.\n"
                f"You now have {new_anti_rob_items_owned} {ANTI_ROB_EMOJI} Anti-Rob Shield(s). "
                f"Use them with a `/use anti-rob` command (coming soon!)"
            )
        else:
            await interaction.followup.send(
                f"❌ '{item}' is not a valid item in the shop. Check `/shop` for available items.", 
                ephemeral=True
            )

    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("Shop MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Shop(bot))