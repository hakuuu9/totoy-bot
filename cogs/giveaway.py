import discord
from discord.ext import commands, tasks
from discord import app_commands
from pymongo import MongoClient
from datetime import datetime, timedelta
import re # For parsing duration string
import random
from config import MONGO_URL # Assuming config.py is in the same directory

# Default emoji for entering the giveaway
GIVEAWAY_EMOJI = "🎉"

# --- New: Confirmation View for Giveaways ---
class ConfirmGiveawayView(discord.ui.View):
    def __init__(self, original_interaction: discord.Interaction):
        super().__init__(timeout=60) # User has 60 seconds to confirm
        self.confirmed = False
        self.original_interaction = original_interaction # Store original interaction for followups if needed

    async def on_timeout(self):
        # This is called if no button is pressed within the timeout
        if not self.confirmed: # Only if they didn't click start
            try:
                # Attempt to edit the original ephemeral message to indicate timeout
                await self.original_interaction.edit_original_response(
                    content="Giveaway setup timed out. Please run the command again.",
                    view=None, embed=None
                )
            except discord.NotFound:
                # Original message might have been deleted already, ignore.
                pass
            except Exception as e:
                print(f"Error during giveaway confirmation timeout handling: {e}")

    @discord.ui.button(label="Start Giveaway", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can confirm this giveaway.", ephemeral=True)
            return

        self.confirmed = True
        # Edit the ephemeral message to acknowledge confirmation
        await interaction.response.edit_message(content="Giveaway confirmed! Launching...", view=None, embed=None)
        self.stop() # Stop waiting for interactions

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can cancel this giveaway.", ephemeral=True)
            return

        self.confirmed = False # Set to False to indicate cancellation
        # Edit the ephemeral message to acknowledge cancellation
        await interaction.response.edit_message(content="Giveaway cancelled.", view=None, embed=None)
        self.stop() # Stop waiting for interactions

# --- End Confirmation View ---

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = MongoClient(MONGO_URL)
        self.giveaway_db = self.client.hxhbot.giveaways 
        self.user_db = self.client.hxhbot.users 

        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()
        self.client.close()
        print("Giveaway MongoDB client closed.")

    # --- Helper function to parse duration string (e.g., "1h30m", "2d") ---
    def parse_duration(self, duration_str: str) -> timedelta:
        total_seconds = 0
        matches = re.findall(r'(\d+)([dhms])', duration_str.lower())
        
        if not matches:
            raise ValueError("Invalid duration format. Use e.g., '1h', '30m', '2d', '1d12h'.")

        for value, unit in matches:
            value = int(value)
            if unit == 'd':
                total_seconds += value * 86400
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 's':
                total_seconds += value
        
        if total_seconds <= 0:
            raise ValueError("Duration must be greater than zero.")
            
        return timedelta(seconds=total_seconds)

    @app_commands.command(name="giveaway", description="Start a new giveaway!")
    @app_commands.describe(
        name="The name/description of the prize.",
        duration="How long the giveaway will last (e.g., 1h, 30m, 2d, 1d12h).",
        winners="The number of winners for this giveaway (minimum 1).",
        required_role="A role users must have to enter (optional).",
        extra_entry_role="A role whose members get more entries (optional).",
        extra_entries_for_role="The total entries members with the extra role get (e.g., 2 for 1 extra entry). Defaults to 2. Max 10.",
        image_url="An image URL to display in the giveaway embed (optional).",
        embed_color_hex="A hex code for the embed color (e.g., #FF0000, optional)."
    )
    async def giveaway(
        self, 
        interaction: discord.Interaction, 
        name: str, 
        duration: str, 
        winners: int, 
        required_role: discord.Role = None, 
        extra_entry_role: discord.Role = None,
        extra_entries_for_role: app_commands.Range[int, 2, 10] = None, # Range from 2 to 10
        image_url: str = None, 
        embed_color_hex: str = None
    ):
        await interaction.response.defer(ephemeral=True) # Defer the initial response

        # --- Input Validation (All same as before) ---
        if winners <= 0:
            return await interaction.followup.send("❌ The number of winners must be at least 1.", ephemeral=True)

        try:
            giveaway_duration = self.parse_duration(duration)
        except ValueError as e:
            return await interaction.followup.send(f"❌ Invalid duration format: {e}", ephemeral=True)

        if giveaway_duration < timedelta(seconds=10): 
            return await interaction.followup.send("❌ Giveaway duration must be at least 10 seconds.", ephemeral=True)

        embed_color = discord.Color.gold()
        if embed_color_hex:
            embed_color_hex = embed_color_hex.lstrip("#")
            try:
                embed_color = discord.Color(int(embed_color_hex, 16))
            except ValueError:
                return await interaction.followup.send("❌ Invalid hex color format. Use e.g., `#FF0000` or `FF0000`.", ephemeral=True)

        if extra_entry_role:
            if extra_entries_for_role is None:
                extra_entries_for_role = 2 
            if required_role and extra_entry_role.id == required_role.id:
                return await interaction.followup.send("❌ The `extra_entry_role` cannot be the same as the `required_role`.", ephemeral=True)
        elif extra_entries_for_role is not None:
             return await interaction.followup.send("❌ You must specify an `extra_entry_role` if you set `extra_entries_for_role`.", ephemeral=True)


        end_time = datetime.utcnow() + giveaway_duration
        
        # --- Create Giveaway Embed (This is the preview embed) ---
        giveaway_embed = discord.Embed(
            title="🎉 GIVEAWAY! 🎉",
            description=f"**Prize:** {name}\n\n"
                        f"React with {GIVEAWAY_EMOJI} to enter!",
            color=embed_color,
            timestamp=end_time
        )
        giveaway_embed.add_field(name="Winners", value=f"{winners}", inline=True)
        giveaway_embed.add_field(name="Ends In", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)

        if required_role:
            giveaway_embed.add_field(name="Required Role", value=required_role.mention, inline=False)
        
        if extra_entry_role:
            giveaway_embed.add_field(
                name="Extra Entries",
                value=f"Members with {extra_entry_role.mention} get **{extra_entries_for_role} entries**!",
                inline=False
            )
            
        if image_url:
            giveaway_embed.set_image(url=image_url)

        giveaway_embed.set_footer(text=f"Giveaway ends at")

        # --- NEW: Send Confirmation Message with Buttons ---
        view = ConfirmGiveawayView(interaction) # Pass the original interaction to the view
        confirmation_message_content = "Here's a **preview** of your giveaway. Please review and click 'Start Giveaway' to launch, or 'Cancel' to abort:"
        try:
            # Send an ephemeral message with the preview and buttons
            await interaction.followup.send(
                content=confirmation_message_content, 
                embed=giveaway_embed, 
                view=view, 
                ephemeral=True # Crucially, this message is ephemeral
            )
            # Wait for the user to click a button (or for the timeout)
            await view.wait() 
        except Exception as e:
            print(f"Error during giveaway confirmation message or waiting for view: {e}")
            return await interaction.followup.send(f"❌ An error occurred during confirmation: {e}", ephemeral=True)


        # --- Process Confirmation Result ---
        if view.confirmed:
            # User clicked 'Start Giveaway'
            # --- Send Actual Giveaway Message to the Channel ---
            try:
                giveaway_message = await interaction.channel.send(embed=giveaway_embed)
                await giveaway_message.add_reaction(GIVEAWAY_EMOJI)
            except discord.Forbidden:
                # If bot lacks permission to send the actual message, inform user
                await interaction.followup.send( 
                    "❌ I don't have permissions to send messages or add reactions in this channel. "
                    "Giveaway cancelled. Please check my permissions.", ephemeral=True
                )
                return
            except Exception as e:
                print(f"Error sending actual giveaway message: {e}")
                await interaction.followup.send(f"❌ An error occurred while launching the giveaway: {e}. Giveaway cancelled.", ephemeral=True)
                return

            # --- Store Giveaway Data in Database ---
            giveaway_data = {
                "_id": str(giveaway_message.id), # Message ID as unique identifier
                "channel_id": str(interaction.channel.id),
                "guild_id": str(interaction.guild.id),
                "end_time": end_time,
                "winner_count": winners,
                "required_role_id": str(required_role.id) if required_role else None,
                "extra_entry_role_id": str(extra_entry_role.id) if extra_entry_role else None, 
                "extra_entries_for_role": extra_entries_for_role if extra_entry_role else None, 
                "giveaway_name": name,
                "host_id": str(interaction.user.id),
                "is_ended": False 
            }
            self.giveaway_db.insert_one(giveaway_data)

            # Inform user that giveaway is launched (this will be a new ephemeral message or edit the previous one)
            # The view.stop() handles the original ephemeral message state, so a new followup is fine.
            await interaction.followup.send(f"✅ Giveaway for **{name}** has been launched in {interaction.channel.mention}!", ephemeral=True)

        else:
            # User clicked 'Cancel' or timeout occurred.
            # The view's `cancel_button` or `on_timeout` methods already handled updating the ephemeral message.
            pass


    # --- Background task to check for ended giveaways (No changes needed here for functionality) ---
    @tasks.loop(minutes=1) 
    async def check_giveaways(self):
        await self.bot.wait_until_ready()
        
        ended_giveaways = self.giveaway_db.find({
            "end_time": {"$lte": datetime.utcnow()},
            "is_ended": False
        })

        for giveaway_data in ended_giveaways:
            try:
                guild = self.bot.get_guild(int(giveaway_data["guild_id"]))
                if not guild:
                    print(f"Guild {giveaway_data['guild_id']} not found for giveaway {giveaway_data['_id']}. Marking as ended.")
                    self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})
                    continue

                channel = guild.get_channel(int(giveaway_data["channel_id"]))
                if not channel:
                    print(f"Channel {giveaway_data['channel_id']} not found for giveaway {giveaway_data['_id']}. Marking as ended.")
                    self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})
                    continue

                try:
                    giveaway_message = await channel.fetch_message(int(giveaway_data["_id"]))
                except discord.NotFound:
                    print(f"Giveaway message {giveaway_data['_id']} not found. Marking as ended.")
                    self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})
                    continue
                except discord.Forbidden:
                    print(f"Missing permissions to fetch message {giveaway_data['_id']}. Skipping.")
                    self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})
                    continue

                all_reactors = []
                for reaction in giveaway_message.reactions:
                    if str(reaction.emoji) == GIVEAWAY_EMOJI:
                        async for user in reaction.users():
                            if not user.bot:
                                all_reactors.append(user)
                        break

                final_participant_list = []
                required_role_id = giveaway_data.get("required_role_id")
                extra_entry_role_id = giveaway_data.get("extra_entry_role_id")
                extra_entries_multiplier = giveaway_data.get("extra_entries_for_role", 1) # Default to 1 if not set

                required_role_obj = guild.get_role(int(required_role_id)) if required_role_id else None
                extra_entry_role_obj = guild.get_role(int(extra_entry_role_id)) if extra_entry_role_id else None

                if required_role_id and not required_role_obj:
                    await channel.send(f"⚠️ Warning: The `required_role` for giveaway **'{giveaway_data['giveaway_name']}'** no longer exists. All participants were considered for the base entry.")
                if extra_entry_role_id and not extra_entry_role_obj:
                    await channel.send(f"⚠️ Warning: The `extra_entry_role` for giveaway **'{giveaway_data['giveaway_name']}'** no longer exists. Extra entries for this role will be ignored.")


                for participant_user in all_reactors:
                    member = guild.get_member(participant_user.id)
                    if not member: 
                        continue

                    if required_role_obj and required_role_obj not in member.roles:
                        continue

                    final_participant_list.append(member)

                    if extra_entry_role_obj and extra_entry_role_obj in member.roles:
                        for _ in range(extra_entries_multiplier - 1):
                            final_participant_list.append(member)

                winners = []
                if len(final_participant_list) >= giveaway_data["winner_count"]:
                    winners = random.sample(final_participant_list, giveaway_data["winner_count"])
                else:
                    winners = final_participant_list 

                if winners:
                    winner_mentions = ", ".join([winner.mention for winner in winners])
                    await channel.send(
                        f"🎉 **GIVEAWAY ENDED!** 🎉\n"
                        f"The giveaway for **{giveaway_data['giveaway_name']}** has concluded!\n"
                        f"Congratulations to the winner(s): {winner_mentions}!"
                    )
                else:
                    await channel.send(
                        f"💔 **GIVEAWAY ENDED!** 💔\n"
                        f"The giveaway for **{giveaway_data['giveaway_name']}** has concluded, but there were no eligible participants."
                    )
                
                original_embed = giveaway_message.embeds[0] if giveaway_message.embeds else discord.Embed()
                original_embed.title = "🎉 GIVEAWAY ENDED! 🎉"
                original_embed.description = f"**Prize:** {giveaway_data['giveaway_name']}\n\nThis giveaway has ended."
                original_embed.color = discord.Color.dark_grey() 
                original_embed.set_footer(text="Giveaway ended")
                original_embed.timestamp = datetime.utcnow() 
                
                new_fields = []
                for field in original_embed.fields:
                    if field.name not in ["Winners", "Ends In", "Required Role", "Extra Entries"]:
                        new_fields.append(field)
                original_embed.clear_fields()
                for field in new_fields:
                    original_embed.add_field(name=field.name, value=field.value, inline=field.inline)

                await giveaway_message.edit(embed=original_embed)

                self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})

            except Exception as e:
                print(f"Error processing giveaway {giveaway_data['_id']}: {e}")
                self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
