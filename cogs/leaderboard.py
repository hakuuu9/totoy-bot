import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from config import MONGO_URL

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # IMPORTANT: This must point to the SAME collection where coinflip stores balances
        # Based on your coinflip, this should be 'users' and not 'daily'
        self.client = MongoClient(MONGO_URL)
        self.db = self.client.hxhbot.users # Corrected: Should be 'users' collection

    @app_commands.command(name="leaderboard", description="View the top 20 richest members")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer to prevent timeout

        # IMPORTANT: Sort by "balance" field, not "coins"
        # Ensure the balance is treated as a number in MongoDB for correct sorting
        # If your 'balance' field could be a string, you might need to convert it to int in your database or query
        top_users = list(self.db.find({"balance": {"$exists": True}}).sort("balance", -1).limit(20))
        
        if not top_users:
            return await interaction.followup.send("❌ There are no rich people yet!") # Changed message slightly

        embed = discord.Embed(
            title="<a:lb:1376576752414883953> Kinsay Sikat sa Barya? (Richest Members)",
            description="",
            color=discord.Color.gold() # Changed color for better visibility, adjust as desired
        )

        # Build the description string
        for index, user in enumerate(top_users, start=1):
            user_id = int(user["_id"]) # Ensure user_id is an integer if used with get_member
            member = interaction.guild.get_member(user_id) # Try to get the member from cache
            
            # Use member's display name if found, otherwise fall back to a mention
            name = member.display_name if member else f"<@{user_id}>"
            
            # IMPORTANT: Get balance from the "balance" field, not "coins"
            balance = user.get("balance", 0) 
            
            embed.description += f"**{index}.** {name} — ₱{balance:,}\n" # Added comma formatting for balance

        await interaction.followup.send(embed=embed)

    def cog_unload(self):
        # Good practice: Close the MongoDB client when the cog is unloaded
        self.client.close()
        print("Leaderboard MongoDB client closed.")

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))