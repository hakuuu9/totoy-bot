import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp # For extracting YouTube audio
import asyncio # For async operations

# Suppress warnings from yt-dlp
yt_dlp.utils.bug_reports_message = lambda: ''

# --- YT-DLP Options ---
# These options tell yt-dlp how to extract the audio.
# We want the best audio format, no downloading (just info), and default search for convenience.
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True, # Don't automatically download entire playlists
    'default_search': 'auto', # Allows searching by title if not a URL
    'source_address': '0.0.0.0', # bind to ipv4 since ipv6 can cause issues sometimes
    'verbose': False, # Set to True for more debug info from yt-dlp
    'extract_flat': True, # Extract info without downloading for search results
}

# --- FFmpeg Options ---
# These options are passed to FFmpeg when creating the audio source for Discord.
FFMPEG_OPTIONS = {
    'options': '-vn', # No video (audio only)
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5' # For stream stability
}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # A simple dictionary to keep track of voice clients per guild
        self.voice_clients = {}

    async def get_audio_source(self, query: str):
        """
        Uses yt-dlp to find and return a streamable audio URL.
        """
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            try:
                # Extract info. If it's a search term, get the first result.
                # If it's a URL, get info directly.
                info = ydl.extract_info(query, download=False)

                # For search results, info will be a dict with 'entries' list
                if 'entries' in info:
                    # Take the first entry, as 'default_search': 'auto' gives us a list
                    video_info = info['entries'][0]
                else:
                    # If it's a direct URL, info is already the video_info
                    video_info = info

                # Find the best audio format URL
                audio_url = None
                for fmt in video_info['formats']:
                    if fmt['ext'] == 'm4a' and 'acodec' in fmt and 'mp4a' in fmt['acodec']:
                        audio_url = fmt['url']
                        break
                    elif fmt['vcodec'] == 'none' and 'url' in fmt: # Prioritize audio-only streams
                        audio_url = fmt['url']
                        break
                
                # Fallback to the general 'url' if specific audio formats aren't found
                if not audio_url and 'url' in video_info:
                    audio_url = video_info['url']


                return audio_url, video_info.get('title', 'Unknown Title'), video_info.get('webpage_url', 'No URL')

            except Exception as e:
                print(f"Error extracting info from yt-dlp: {e}")
                return None, None, None

    @app_commands.command(name="play", description="Plays a song from YouTube or a URL.")
    @app_commands.describe(query="The song title or YouTube URL to play.")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=False, thinking=True)

        user_voice_channel = interaction.user.voice.channel if interaction.user.voice else None

        if not user_voice_channel:
            await interaction.followup.send("You need to be in a voice channel to use this command!", ephemeral=True)
            return

        guild_id = interaction.guild_id

        # If bot is not in a voice channel in this guild, join it
        if guild_id not in self.voice_clients or not self.voice_clients[guild_id].is_connected():
            try:
                voice_client = await user_voice_channel.connect()
                self.voice_clients[guild_id] = voice_client
                await interaction.followup.send(f"Joined {user_voice_channel.mention}!")
            except discord.ClientException:
                await interaction.followup.send("I'm already trying to connect to a voice channel or already in one. Please try again or use `/stop`.", ephemeral=True)
                return
            except asyncio.TimeoutError:
                await interaction.followup.send("Could not connect to the voice channel in time.", ephemeral=True)
                return
        else:
            # If bot is in a different channel, move to the user's channel
            if self.voice_clients[guild_id].channel != user_voice_channel:
                await self.voice_clients[guild_id].move_to(user_voice_channel)
                await interaction.followup.send(f"Moved to {user_voice_channel.mention}!")

        voice_client = self.voice_clients[guild_id]

        if voice_client.is_playing():
            await interaction.followup.send("I'm already playing something. This bot currently only supports playing one song at a time. Use `/stop` first if you want to play a new song.", ephemeral=True)
            return

        audio_url, title, webpage_url = await self.get_audio_source(query)

        if not audio_url:
            await interaction.followup.send(f"❌ Could not find audio for '{query}'. Please try a different query or a direct YouTube URL.", ephemeral=True)
            return

        try:
            # Create an FFmpeg audio source
            source = discord.FFmpegOpusAudio(audio_url, **FFMPEG_OPTIONS)
            voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

            # Inform the user what's playing
            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"[{title}]({webpage_url})",
                color=discord.Color.blue()
            )
            embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            embed.set_footer(text=f"Playing in {user_voice_channel.name}")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"An error occurred while trying to play the audio: {e}", ephemeral=True)
            print(f"Error during audio playback: {e}")

    @app_commands.command(name="stop", description="Stops the current music and disconnects the bot from voice.")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild_id

        if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
            voice_client = self.voice_clients[guild_id]
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            del self.voice_clients[guild_id]
            await interaction.followup.send("⏹️ Stopped playing and disconnected from voice channel.")
        else:
            await interaction.followup.send("❌ I'm not currently in a voice channel in this server.", ephemeral=True)

    @app_commands.command(name="leave", description="Alias for /stop. Disconnects the bot from voice.")
    async def leave_voice(self, interaction: discord.Interaction):
        await self.stop(interaction) # Call the stop command's logic

async def setup(bot):
    await bot.add_cog(Music(bot))
