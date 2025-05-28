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

# View for Hangman guesses (buttons)
class HangmanGuessView(discord.ui.View):
    def __init__(self, game_instance, current_player_id: int | None):
        super().__init__(timeout=120)  # Timeout after 2 minutes of inactivity for a guess
        self.game = game_instance
        self.current_player_id = current_player_id # None for FFA mode

    # This check ensures only the current player (in solo/duo) can use the buttons.
    # In FFA mode (self.game.players is None), anyone can use them.
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.game.players is not None and interaction.user.id != self.current_player_id:
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Guess a Letter", style=discord.ButtonStyle.primary, custom_id="hangman_guess_letter_btn")
    async def guess_letter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Respond by sending the Guess Letter Modal
        await interaction.response.send_modal(HangmanGuessModal(self.game))

    @discord.ui.button(label="Solve Word", style=discord.ButtonStyle.secondary, custom_id="hangman_solve_word_btn")
    async def solve_word_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Respond by sending the Solve Word Modal
        await interaction.response.send_modal(HangmanSolveModal(self.game))

# Modal for guessing a single letter
class HangmanGuessModal(discord.ui.Modal, title="Guess a Letter"):
    def __init__(self, game_instance):
        super().__init__(timeout=300) # Modal timeout after 5 minutes
        self.game = game_instance

    # Text input field for the guess
    guess_input = discord.ui.TextInput(
        label="Enter your letter guess",
        placeholder="e.g., 'a', 'b', 'c'",
        max_length=1, # Only one character allowed
        min_length=1,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.guess_input.value.lower()
        
        # Validate input: must be an alphabet letter
        if not guess.isalpha():
            await interaction.response.send_message("❌ Your guess must be a letter!", ephemeral=True)
            return

        # Check if letter was already guessed
        if guess in self.game.guessed_letters:
            await interaction.response.send_message(f"⚠️ You already guessed `{guess}`!", ephemeral=True)
            return

        self.game.guessed_letters.add(guess) # Add to set of guessed letters
        
        # Process the guess
        if guess in self.game.word:
            for i, c in enumerate(self.game.word):
                if c == guess:
                    self.game.display[i] = guess # Reveal letter in display
            message_for_update = f"✅ Correct! `{self.game.format_display()}`"
        else:
            self.game.attempts_left -= 1 # Decrement attempts
            message_for_update = f"❌ Wrong! `{self.game.format_display()}`\nTries left: {self.game.attempts_left}\n{HANGMAN_STAGES[MAX_ATTEMPTS - self.game.attempts_left]}"

        # Update the main game message and check for game end conditions
        await self.game.update_game_state(interaction, message_for_update)

# Modal for solving the entire word
class HangmanSolveModal(discord.ui.Modal, title="Solve the Word"):
    def __init__(self, game_instance):
        super().__init__(timeout=300) # Modal timeout after 5 minutes
        self.game = game_instance

    # Text input field for the full word guess
    solve_input = discord.ui.TextInput(
        label="Enter your full word guess",
        placeholder="Type the entire word here",
        min_length=1,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.solve_input.value.lower()

        # Check if the guessed word is correct
        if guess == self.game.word:
            self.game.display = list(self.game.word) # Reveal the full word
            message_for_update = f"🎉 **{interaction.user.mention} Solved it!** The word was: `{self.game.word}`"
            await self.game.update_game_state(interaction, message_for_update, game_won=True)
        else:
            self.game.attempts_left -= 1 # Incorrect guess, lose an attempt
            message_for_update = f"❌ Wrong word! `{self.game.format_display()}`\nTries left: {self.game.attempts_left}\n{HANGMAN_STAGES[MAX_ATTEMPTS - self.game.attempts_left]}"
            await self.game.update_game_state(interaction, message_for_update)


# Represents a single instance of a Hangman game
class HangmanGame:
    def __init__(self, channel: discord.TextChannel, word: str, players: list[discord.Member] | None):
        self.channel = channel # The channel where the game is being played
        self.word = word
        self.display = ["_" for _ in word] # The masked word shown to players
        self.guessed_letters = set() # Set to store all guessed letters
        self.attempts_left = MAX_ATTEMPTS # Remaining attempts
        self.players = players # List of players (solo/duo) or None (ffa)
        self.current_turn_index = 0 # To track whose turn it is in solo/duo
        self.message = None # To store the main game message, allowing edits

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
        await self.send_turn_message() # Send the first turn prompt and buttons

    async def send_turn_message(self):
        """Updates the game message with the current turn information."""
        current_player_obj = None
        current_player_id = None
        if self.players: # Solo or Duo mode
            current_player_obj = self.players[self.current_turn_index % len(self.players)]
            current_player_id = current_player_obj.id
            turn_prompt = f"🔁 {current_player_obj.mention}, it's your turn to guess."
        else: # FFA mode
            turn_prompt = "Guess a letter or the full word!"
            current_player_id = None # No specific player ID for FFA interaction_check

        # Edit the main game message to update player turn and view
        # We split the content to preserve the initial game details and replace the dynamic turn prompt
        base_content_parts = self.message.content.split('\n\n🔁')
        new_content = base_content_parts[0].strip() + "\n\n" + turn_prompt
        
        # Create and attach the HangmanGuessView with buttons
        view_to_attach = HangmanGuessView(self, current_player_id)
        await self.message.edit(content=new_content, view=view_to_attach)


    async def update_game_state(self, interaction: discord.Interaction, message_from_guess: str, game_won: bool = False):
        """
        Updates the main game message with the latest state after a guess.
        Handles win/loss conditions.
        """
        # Check for game end conditions
        if game_won or "_" not in self.display:
            final_message_content = f"🎉 **GAME WON!** The word was: `{self.word}`"
            # Edit the original message to show final state and remove buttons
            await self.message.edit(content=final_message_content, view=None)
            await interaction.response.send_message(message_from_guess, ephemeral=True) # Send modal response
            return

        if self.attempts_left <= 0:
            final_message_content = f"💀 **GAME OVER!** You ran out of tries. The word was: `{self.word}`"
            # Edit the original message to show final state and remove buttons
            await self.message.edit(content=final_message_content, view=None)
            await interaction.response.send_message(message_from_guess, ephemeral=True) # Send modal response
            return

        # If game is still ongoing, prepare updated content for the main message
        current_stage_art = HANGMAN_STAGES[MAX_ATTEMPTS - self.attempts_left]
        
        # Construct the new content for the main game message
        new_main_message_content = (
            f"🎯 **Hangman Game Started!**\n"
            f"Word: `{self.format_display()}`\n"
            f"Guessed Letters: `{', '.join(sorted(list(self.guessed_letters))) or 'None'}`\n"
            f"Tries left: {self.attempts_left}\n"
            f"{current_stage_art}"
        )

        next_player_obj = None
        next_player_id = None
        if self.players: # Solo or Duo mode
            self.current_turn_index += 1 # Advance turn
            next_player_obj = self.players[self.current_turn_index % len(self.players)]
            next_player_id = next_player_obj.id
            new_main_message_content += f"\n\n🔁 {next_player_obj.mention}, it's your turn to guess."
        else: # FFA mode
            new_main_message_content += "\n\nGuess a letter or the full word!"
            next_player_id = None # No specific player ID for FFA

        # Edit the main game message
        await self.message.edit(content=new_main_message_content, view=HangmanGuessView(self, next_player_id))
        
        # Respond to the modal interaction (this is important to dismiss the modal)
        # You can choose to send a visible message or just dismiss it
        await interaction.response.send_message(message_from_guess, ephemeral=True)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionary to store active games by channel ID
        # This prevents multiple games in the same channel and helps manage game instances.
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
    async def hangman(self, interaction: discord.Interaction, mode: str, opponent: discord.Member = None):
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
        game = HangmanGame(interaction.channel, word, players_for_game)
        # Store the game instance in the active_games dictionary
        self.active_games[interaction.channel_id] = game

        # Start the game (sends the initial message and sets up the first turn)
        await game.start()

        # Monitor the game until it ends (either by winning or losing)
        # This loop keeps the game instance alive and allows the cog to manage its lifecycle.
        while True:
            # Game ends if the word is fully guessed or attempts run out
            if "_" not in game.display or game.attempts_left <= 0:
                break # Exit the loop, game is over
            await asyncio.sleep(5) # Check game state every 5 seconds

        # Game has ended, clean up the active game instance from the dictionary
        del self.active_games[interaction.channel_id]
        print(f"Hangman game in channel {interaction.channel_id} ended and cleaned up.")

# This function is called by the bot when loading the cog
async def setup(bot):
    await bot.add_cog(Hangman(bot))
