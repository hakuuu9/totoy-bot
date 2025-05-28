import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import random

# Hangman stages (ASCII art) - expanded for more attempts
HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",  # 0
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",  # 1
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",  # 2
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",  # 3
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",  # 4
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",  # 5
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",  # 6 (Default from your code, 6 attempts remaining)
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n=========```", # 7 (for 5 stages left) - if needed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  /   |\n=========```", # 8 (for 4 stages left) - if needed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  / \\ |\n=========```", # 9 (for 3 stages left) - if needed
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n  |   |\n  / \\ |\n=========\n  (DEAD)```", # 10+ (final stage, adjust as needed)
]

# Max attempts, ensuring it doesn't exceed the number of stages - 1 (for the initial empty gallows)
MAX_ATTEMPTS = len(HANGMAN_STAGES) - 1 # Now 10 attempts if using all 11 stages (0-10)

# View for Hangman guesses (buttons)
class HangmanGuessView(discord.ui.View):
    def __init__(self, game_instance, current_player_id: int):
        super().__init__(timeout=120)  # Timeout after 2 minutes for a guess
        self.game = game_instance
        self.current_player_id = current_player_id
        self.add_item(discord.ui.Button(label="Guess a Letter", style=discord.ButtonStyle.primary, custom_id="hangman_guess_letter"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.game.players and interaction.user.id != self.current_player_id:
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Guess a Letter", style=discord.ButtonStyle.primary, custom_id="hangman_guess_letter_btn")
    async def guess_letter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HangmanGuessModal(self.game))

    @discord.ui.button(label="Solve Word", style=discord.ButtonStyle.secondary, custom_id="hangman_solve_word_btn")
    async def solve_word_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HangmanSolveModal(self.game))

# Modal for guessing a single letter
class HangmanGuessModal(discord.ui.Modal, title="Guess a Letter"):
    def __init__(self, game_instance):
        super().__init__()
        self.game = game_instance

    guess_input = discord.ui.TextInput(
        label="Enter your letter guess",
        placeholder="e.g., 'a', 'b', 'c'",
        max_length=1,
        min_length=1,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.guess_input.value.lower()
        if not guess.isalpha():
            await interaction.response.send_message("❌ Your guess must be a letter!", ephemeral=True)
            return

        if guess in self.game.guessed_letters:
            await interaction.response.send_message(f"⚠️ You already guessed `{guess}`!", ephemeral=True)
            return

        self.game.guessed_letters.add(guess)
        
        # Check if correct
        if guess in self.game.word:
            for i, c in enumerate(self.game.word):
                if c == guess:
                    self.game.display[i] = guess
            message = f"✅ Correct! `{self.game.format_display()}`"
        else:
            self.game.attempts_left -= 1
            message = f"❌ Wrong! `{self.game.format_display()}`\nTries left: {self.game.attempts_left}\n{HANGMAN_STAGES[MAX_ATTEMPTS - self.game.attempts_left]}"

        # Update and check game state
        await self.game.update_game_state(interaction, message)

# Modal for solving the entire word
class HangmanSolveModal(discord.ui.Modal, title="Solve the Word"):
    def __init__(self, game_instance):
        super().__init__()
        self.game = game_instance

    solve_input = discord.ui.TextInput(
        label="Enter your full word guess",
        placeholder="Type the entire word here",
        min_length=1,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.solve_input.value.lower()

        if guess == self.game.word:
            self.game.display = list(self.game.word) # Fill in the word
            message = f"🎉 **{interaction.user.mention} Solved it!** The word was: `{self.game.word}`"
            await self.game.update_game_state(interaction, message, game_won=True)
        else:
            self.game.attempts_left -= 1
            message = f"❌ Wrong word! `{self.game.format_display()}`\nTries left: {self.game.attempts_left}\n{HANGMAN_STAGES[MAX_ATTEMPTS - self.game.attempts_left]}"
            await self.game.update_game_state(interaction, message)


class HangmanGame:
    def __init__(self, ctx: commands.Context, word: str, players: list[discord.Member]):
        self.ctx = ctx
        self.word = word
        self.display = ["_" for _ in word]
        self.guessed_letters = set()
        self.attempts_left = MAX_ATTEMPTS
        self.players = players # List of players (for duo/solo) or None (for ffa)
        self.current_turn_index = 0
        self.message = None # To store the game message for editing

    def format_display(self):
        return " ".join(self.display)

    async def start(self):
        initial_message_content = (
            f"🎯 **Hangman Game Started!**\n"
            f"Word: `{self.format_display()}`\n"
            f"You have {self.attempts_left} tries.\n"
            f"{HANGMAN_STAGES[0]}"
        )
        if self.players:
            initial_message_content += f"\n\n**Players:** {', '.join([p.mention for p in self.players])}"
            
        self.message = await self.ctx.send(initial_message_content)
        await self.send_turn_message()

    async def send_turn_message(self):
        current_player = None
        if self.players:
            current_player = self.players[self.current_turn_index % len(self.players)]
            content = f"🔁 {current_player.mention}, it's your turn to guess."
            view = HangmanGuessView(self, current_player.id)
        else: # FFA mode
            content = "Guess a letter or the full word!"
            view = HangmanGuessView(self, None) # No specific current player for FFA

        # Edit the main game message to update player turn and view
        await self.message.edit(content=self.message.content.split('🔁')[0].strip() + "\n\n" + content, view=view)


    async def update_game_state(self, interaction: discord.Interaction, message: str, game_won: bool = False):
        if game_won or "_" not in self.display:
            final_message = f"🎉 **GAME WON!** The word was: `{self.word}`"
            await self.message.edit(content=final_message, view=None) # Remove buttons
            return

        if self.attempts_left <= 0:
            final_message = f"💀 **GAME OVER!** You ran out of tries. The word was: `{self.word}`"
            await self.message.edit(content=final_message, view=None) # Remove buttons
            return

        # Update the main game message with the current state
        current_stage_art = HANGMAN_STAGES[MAX_ATTEMPTS - self.attempts_left]
        
        # Preserve initial game details, update only the dynamic parts
        base_content = self.message.content.split('Word:')[0] # Get everything before 'Word:'
        
        new_content = (
            f"{base_content.strip()}\n"
            f"Word: `{self.format_display()}`\n"
            f"Guessed Letters: `{', '.join(sorted(list(self.guessed_letters))) or 'None'}`\n"
            f"Tries left: {self.attempts_left}\n"
            f"{current_stage_art}"
        )

        if self.players:
            # Advance turn for next player in duo/solo
            self.current_turn_index += 1
            next_player = self.players[self.current_turn_index % len(self.players)]
            new_content += f"\n\n🔁 {next_player.mention}, it's your turn to guess."
            view = HangmanGuessView(self, next_player.id)
        else: # FFA
            new_content += "\n\nGuess a letter or the full word!"
            view = HangmanGuessView(self, None)


        await interaction.response.edit_message(content=new_content, view=view)


class Hangman(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {} # Stores active games by channel ID

    # Function to fetch a random word from an online API
    async def fetch_word(self) -> str:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://random-word-api.herokuapp.com/word?length=5") as resp: # Added length=5 for shorter words
                    if resp.status == 200:
                        data = await resp.json()
                        word = data[0].lower()
                        # Simple filter for words that might contain non-alphabetic characters from API
                        if word.isalpha():
                            return word
            except aiohttp.ClientError as e:
                print(f"Error fetching word: {e}")
        # Fallback if API fails or word is invalid
        return random.choice(["python", "discord", "hangman", "bot", "code", "challenge", "gemini"])

    @app_commands.command(name="hangman", description="Start a game of Hangman!")
    @app_commands.describe(
        mode="Choose game mode: 'solo' (you vs bot), 'duo' (you vs another player), 'ffa' (free for all in channel).",
        opponent="Select an opponent for 'duo' mode (optional)."
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Solo", value="solo"),
            app_commands.Choice(name="Duo", value="duo"),
            app_commands.Choice(name="Free For All", value="ffa"),
        ]
    )
    async def hangman(self, interaction: discord.Interaction, mode: str, opponent: discord.Member = None):
        if interaction.channel_id in self.active_games:
            await interaction.response.send_message("❌ A Hangman game is already active in this channel!", ephemeral=True)
            return

        # Defer response to allow time for word fetching
        await interaction.response.defer()

        word = await self.fetch_word()
        if not word:
            await interaction.followup.send("❌ Could not fetch a word. Please try again later.")
            return

        players_list = []
        if mode == "solo":
            players_list = [interaction.user]
        elif mode == "duo":
            if opponent and opponent != interaction.user and not opponent.bot:
                players_list = [interaction.user, opponent]
            else:
                await interaction.followup.send("❌ For 'duo' mode, please specify a valid opponent who is not yourself or a bot.", ephemeral=True)
                return
        elif mode == "ffa":
            players_list = None # Indicates free-for-all, anyone can guess

        game = HangmanGame(interaction.channel, word, players_list)
        self.active_games[interaction.channel_id] = game

        await game.start()

        # Monitor the game until it ends
        while True:
            if "_" not in game.display or game.attempts_left <= 0:
                break # Game over
            await asyncio.sleep(5) # Check every 5 seconds

        # Game has ended, clean up
        del self.active_games[interaction.channel_id]
        print(f"Hangman game in channel {interaction.channel_id} ended and cleaned up.")


async def setup(bot):
    await bot.add_cog(Hangman(bot))
