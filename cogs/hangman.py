# hangman_cog.py (or hangman.py)

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import random

# Hangman stages (ASCII art) - expanded for more attempts
HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",  # 0 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",  # 1 attempt failed
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",  # 2 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",  # 3 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",  # 4 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",  # 5 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",  # 6 attempts failed (full body, classic 6-try)
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |\n=========```", # 7 attempts failed (extra details if you want more tries)
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  /   |\n=========```", # 8 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  / \\ |\n=========```", # 9 attempts failed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  / \\ |\n=========\n  (DEAD)```", # 10 attempts failed (final, lose state)
]

# Max attempts allowed. Must be `len(HANGMAN_STAGES) - 1` because index 0 is the initial state.
MAX_ATTEMPTS = len(HANGMAN_STAGES) - 1 # This will be 10 if you use all 11 stages (0-10)

# Represents a single instance of a Hangman game
class HangmanGame:
    def __init__(self, bot, channel: discord.TextChannel, word: str, players: list[discord.Member] | None):
        self.bot = bot # Need bot instance to use wait_for
        self.channel = channel # The channel where the game is being played
        self.word = word
        self.display = ["_" for _ in word] # The masked word shown to players
        self.guessed_letters = set() # Set to store all guessed letters
        self.attempts_left = MAX_ATTEMPTS # Remaining attempts
        self.players = players # List of players (solo/duo) or None (ffa)
        self.current_turn_index = 0 # To track whose turn it is in solo/duo
        self.message = None # To store the main game message, allowing edits
        self.is_stopped = False # Flag to indicate if the game has been stopped externally

    def format_display(self):
        """Returns the current state of the word, e.g., "_ y t _ _ n" """
        return " ".join(self.display)

    async def start(self):
        """Sends the initial game message and starts the game loop."""
        initial_message_content = (
            f"🎯 **Hangman Game Started!**\n"
            f"Word: `{self.format_display()}`\n"
            f"Guessed Letters: `{', '.join(sorted(list(self.guessed_letters))) or 'None'}`\n"
            f"You have {self.attempts_left} tries.\n"
            f"{HANGMAN_STAGES[0]}" # Initial gallows state
        )
        if self.players:
            initial_message_content += f"\n\n**Players:** {', '.join([p.mention for p in self.players])}"
            
        # Send the first message, which will be edited throughout the game
        self.message = await self.channel.send(initial_message_content)
        await self.game_loop()

    async def game_loop(self):
        """Main loop for the Hangman game, handling turns and guesses."""
        while self.attempts_left > 0 and "_" in self.display and not self.is_stopped:
            current_player_obj = None
            if self.players: # Solo or Duo mode
                current_player_obj = self.players[self.current_turn_index % len(self.players)]
                await self.message.edit(content=self.get_game_state_message() + f"\n\n🔁 {current_player_obj.mention}, it's your turn to guess a letter or the full word.")
                
            else: # FFA mode
                await self.message.edit(content=self.get_game_state_message() + "\n\nGuess a letter or the full word!")

            try:
                # Wait for a message in the channel
                guess_msg = await self.bot.wait_for(
                    "message",
                    timeout=60, # 60 seconds to guess
                    check=lambda m: (
                        m.channel == self.channel and # Must be in the game channel
                        m.content.strip().lower() != "/hangman" and # Ignore new game commands
                        m.content.strip().lower() != "/hangman stop" and # Ignore stop commands
                        (self.players is None or m.author == current_player_obj) # If turn-based, only current player
                    )
                )
            except asyncio.TimeoutError:
                if not self.is_stopped: # Only send timeout if not stopped by command
                    await self.message.edit(content=f"⏰ Time's up! Game over. The word was: `{self.word}`", view=None)
                break # Exit game loop
            
            # If the game was stopped while waiting for input, break out
            if self.is_stopped:
                break

            # Delete the user's guess message to keep the channel clean
            try:
                await guess_msg.delete()
            except discord.Forbidden:
                pass # Bot might not have permission to delete messages

            guess = guess_msg.content.lower().strip()

            if not guess.isalpha():
                await self.channel.send("❌ Your guess must be alphabetic (a letter or a word)!", delete_after=5)
                continue

            if len(guess) == 1: # Single letter guess
                if guess in self.guessed_letters:
                    await self.channel.send(f"⚠️ You already guessed `{guess}`!", delete_after=5)
                    continue

                self.guessed_letters.add(guess)
                if guess in self.word:
                    for i, c in enumerate(self.word):
                        if c == guess:
                            self.display[i] = guess
                    await self.channel.send(f"✅ Correct! `{guess}` was in the word.", delete_after=5)
                else:
                    self.attempts_left -= 1
                    await self.channel.send(f"❌ Wrong! `{guess}` was not in the word.", delete_after=5)
            else: # Full word guess
                if guess == self.word:
                    self.display = list(self.word) # Reveal the full word
                    await self.channel.send(f"🎉 **{guess_msg.author.mention} Solved it!** The word was: `{self.word}`")
                    break # Game won
                else:
                    self.attempts_left -= 1
                    await self.channel.send(f"❌ Wrong word! `{guess}` was not the word.", delete_after=5)
            
            # Advance turn for next player in solo/duo
            if self.players:
                self.current_turn_index += 1
            
            # Update the main game message after each guess
            if not self.is_stopped: # Only update if not stopped externally
                await self.message.edit(content=self.get_game_state_message())

        # Game ended (win, lose, or stopped)
        if self.is_stopped:
            final_message_content = f"🛑 The Hangman game was stopped by command. The word was: `{self.word}`"
        elif "_" not in self.display:
            final_message_content = f"🎉 **GAME WON!** The word was: `{self.word}`"
        else:
            final_message_content = f"💀 **GAME OVER!** You ran out of tries. The word was: `{self.word}`"
        
        await self.message.edit(content=final_message_content, view=None) # Ensure buttons are gone

    def get_game_state_message(self):
        """Constructs the current state message of the game."""
        current_stage_art = HANGMAN_STAGES[MAX_ATTEMPTS - self.attempts_left]
        
        content = (
            f"🎯 **Hangman Game Started!**\n"
            f"Word: `{self.format_display()}`\n"
            f"Guessed Letters: `{', '.join(sorted(list(self.guessed_letters))) or 'None'}`\n"
            f"Tries left: {self.attempts_left}\n"
            f"{current_stage_art}"
        )
        if self.players:
            content += f"\n\n**Players:** {', '.join([p.mention for p in self.players])}"
        return content

    async def stop_game(self, stopper: discord.Member):
        """Forcefully stops the game."""
        self.is_stopped = True
        # Wake up the wait_for loop if it's currently waiting
        if self.bot and hasattr(self.bot, '_connection') and self.message:
            # Send a dummy message to trigger the check and let the loop break
            # This is a bit of a hack, but ensures the wait_for finishes quickly
            await self.channel.send(f"Game is stopping...", delete_after=0.1)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store active games by channel ID
        self.active_games = {} 

    # Helper function to fetch a random word from an online API
    async def fetch_word(self) -> str:
        async with aiohttp.ClientSession() as session:
            try:
                # Request a word of length 5 to 9 for better gameplay experience
                async with session.get("https://random-word-api.herokuapp.com/word?length=5&min=5&max=9") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        word = data[0].lower()
                        # Basic validation to ensure the word contains only alphabetic characters
                        if word.isalpha():
                            return word
            except aiohttp.ClientError as e:
                print(f"Error fetching word from API: {e}")
            # Fallback to a hardcoded list if API fails or returns an invalid word
            return random.choice(["python", "discord", "hangman", "bot", "code", "challenge", "gemini", "developer", "program"])

    @app_commands.command(name="hangman", description="Start a game of Hangman!")
    @app_commands.describe(
        mode="Choose game mode: 'solo' (you vs bot), 'duo' (you vs another player), 'ffa' (free for all in channel).",
        opponent="Select an opponent for 'duo' mode (optional)."
    )
    # Define choices for the 'mode' argument, providing user-friendly names and internal values
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Solo (You vs Bot)", value="solo"),
            app_commands.Choice(name="Duo (You vs Another Player)", value="duo"),
            app_commands.Choice(name="Free For All (Anyone can guess)", value="ffa"),
        ]
    )
    async def start_hangman(self, interaction: discord.Interaction, mode: str, opponent: discord.Member = None): # Renamed command for clarity with subcommand
        # Check if a game is already active in this channel
        if interaction.channel_id in self.active_games:
            await interaction.response.send_message("❌ A Hangman game is already active in this channel! Please wait for it to finish.", ephemeral=True)
            return

        # Defer the response to give time for fetching the word and setting up the game
        # This prevents the "Interaction failed" message if setup takes a moment.
        await interaction.response.defer()

        word = await self.fetch_word()
        if not word:
            await interaction.followup.send("❌ Could not fetch a word. Please try again later.", ephemeral=True)
            return

        players_for_game = [] # This list will hold discord.Member objects for solo/duo
        if mode == "solo":
            players_for_game = [interaction.user]
        elif mode == "duo":
            # Validate opponent for duo mode
            if opponent and opponent != interaction.user and not opponent.bot:
                players_for_game = [interaction.user, opponent]
            else:
                await interaction.followup.send("❌ For 'duo' mode, please select a valid opponent who is not yourself or a bot.", ephemeral=True)
                return
        elif mode == "ffa":
            players_for_game = None # Set to None to indicate Free For All mode where anyone can guess

        # Create a new HangmanGame instance for this channel
        game = HangmanGame(self.bot, interaction.channel, word, players_for_game) # Pass bot instance
        # Store the game instance in the active_games dictionary
        self.active_games[interaction.channel_id] = game

        # Send a quick confirmation message to the user who started the game
        await interaction.followup.send(f"✅ Starting a Hangman game in `{mode.upper()}` mode. Check the channel for the game! You have 60 seconds per guess. Use `/hangman stop` to end the game early.", ephemeral=True)

        # Start the game (sends the initial message and enters the game loop)
        await game.start()

        # After game.start() finishes (meaning the game loop has ended), clean up
        if interaction.channel_id in self.active_games: # Ensure it's still there before deleting
            del self.active_games[interaction.channel_id]
            print(f"Hangman game in channel {interaction.channel_id} ended and cleaned up.")


    @app_commands.command(name="stop", description="Stop the current Hangman game in this channel.")
    async def stop_hangman(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # Defer response

        game_id = interaction.channel_id
        if game_id not in self.active_games:
            await interaction.followup.send("❌ No Hangman game is currently active in this channel.", ephemeral=True)
            return

        game = self.active_games[game_id]
        
        # Optionally, you could add permission checks here, e.g., only the game starter or a mod can stop it.
        # For simplicity, anyone can stop it for now.

        await game.stop_game(interaction.user) # Call the stop method on the game instance
        
        # The game.stop_game() will handle updating the message and breaking the loop.
        # We just need to remove it from our active games list.
        if game_id in self.active_games: # Check again, just in case the game loop finished very quickly
            del self.active_games[game_id]
            print(f"Hangman game in channel {game_id} stopped by {interaction.user.name} and cleaned up.")

        await interaction.followup.send("🛑 Hangman game has been stopped.", ephemeral=True)


# This function is called by the bot when loading the cog
async def setup(bot):
    await bot.add_cog(Hangman(bot))
