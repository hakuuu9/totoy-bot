import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
import re # Import regex for URL validation

class TikTok(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tiktok", description="Download a TikTok video without watermark!")
    @app_commands.describe(url="The URL of the TikTok video.")
    async def tiktok(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(thinking=True, ephemeral=False) # Defer the response

        # Basic URL validation to ensure it's a TikTok URL
        if not re.match(r"https?://(www\.)?(tiktok\.com|vm\.tiktok\.com|m\.tiktok\.com)/", url):
            await interaction.followup.send("❌ That doesn't look like a valid TikTok URL.", ephemeral=True)
            return

        try:
            # Use aiohttp for asynchronous requests within a cog
            async with aiohttp.ClientSession() as session:
                api_url = f"https://tikwm.com/api/?url={url}"
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ Failed to fetch data from TikTok API (Status: {resp.status}).", ephemeral=True)
                        return
                    data = await resp.json()

            if data.get("code") != 0: # tikwm.com API returns code 0 for success
                error_msg = data.get("msg", "Unknown error from API.")
                await interaction.followup.send(f"❌ TikTok API returned an error: {error_msg}", ephemeral=True)
                return

            video_data = data.get("data")
            if not video_data:
                await interaction.followup.send("❌ No video data found in the TikTok API response.", ephemeral=True)
                return

            # Prioritize `nwm_play` (no watermark) or fall back to `play`
            video_url = video_data.get("nwm_play") or video_data.get("play")
            title = video_data.get("title", "TikTok Video")

            if not video_url:
                await interaction.followup.send("❌ Could not find a downloadable video URL.", ephemeral=True)
                return

            # Download the video as bytes using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as video_resp:
                    if video_resp.status != 200:
                        await interaction.followup.send(f"❌ Failed to download video (Status: {video_resp.status}).", ephemeral=True)
                        return
                    video_bytes = io.BytesIO(await video_resp.read())

            # Send the video directly to Discord
            # Use a simple filename for consistency, Discord will handle displaying the content type
            await interaction.followup.send(
                content=f"**{title}**",
                file=discord.File(video_bytes, filename="tiktok_video.mp4")
            )

        except aiohttp.ClientError as e:
            await interaction.followup.send(f"❌ A network error occurred: {e}", ephemeral=True)
        except Exception as e:
            # Catch all other unexpected errors
            await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)
            print(f"Error in TikTok command: {e}") # Log the full error for debugging

async def setup(bot):
    await bot.add_cog(TikTok(bot))
