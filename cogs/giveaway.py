import discord
from discord.ext import commands, tasks
from discord import app_commands
from pymongo import MongoClient
from datetime import datetime, timedelta
import re
import random
from config import MONGO_URL

GIVEAWAY_EMOJI = "🎉"

class ConfirmGiveawayView(discord.ui.View):
    def __init__(self, original_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.confirmed = False
        self.original_interaction = original_interaction

    async def on_timeout(self):
        if not self.confirmed:
            try:
                await self.original_interaction.edit_original_response(
                    content="Giveaway setup timed out. Please run the command again.",
                    view=None, embed=None
                )
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"Error during giveaway confirmation timeout handling: {e}")

    @discord.ui.button(label="Start Giveaway", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can confirm this giveaway.", ephemeral=True)
            return

        self.confirmed = True
        await interaction.response.edit_message(content="Giveaway confirmed! Launching...", view=None, embed=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can cancel this giveaway.", ephemeral=True)
            return

        self.confirmed = False
        await interaction.response.edit_message(content="Giveaway cancelled.", view=None, embed=None)
        self.stop()

class ParticipantsView(discord.ui.View):
    def __init__(self, participants: list[discord.Member], original_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.participants = participants
        self.original_interaction = original_interaction
        self.current_page = 0
        self.pages = self.create_participant_pages()

    def create_participant_pages(self):
        if not self.participants:
            return ["No participants found for this giveaway."]

        # Sort participants alphabetically by their display name
        sorted_participants = sorted(self.participants, key=lambda m: m.display_name.lower())

        # Group participants into pages of 10
        pages = []
        current_page_content = []
        for i, participant in enumerate(sorted_participants):
            current_page_content.append(f"• {participant.mention} (`{participant.id}`)")
            if (i + 1) % 10 == 0 or i == len(sorted_participants) - 1:
                pages.append("\n".join(current_page_content))
                current_page_content = []
        return pages

    async def send_page(self, interaction: discord.Interaction):
        if not self.pages:
            content = "No participants to display."
        else:
            content = f"### Giveaway Participants (Page {self.current_page + 1}/{len(self.pages)})\n\n{self.pages[self.current_page]}"

        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple, emoji="⬅️", row=0)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can navigate this list.", ephemeral=True)
            return

        if self.current_page > 0:
            self.current_page -= 1
        await self.send_page(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, emoji="➡️", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("❌ Only the command issuer can navigate this list.", ephemeral=True)
            return

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
        await self.send_page(interaction)

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
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(
        self,
        interaction: discord.Interaction,
        name: str,
        duration: str,
        winners: int,
        required_role: discord.Role = None,
        extra_entry_role: discord.Role = None,
        extra_entries_for_role: app_commands.Range[int, 2, 10] = None,
        image_url: str = None,
        embed_color_hex: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        # --- Input Validation ---
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
        
        # --- Create Giveaway Embed (UI & Title Changes) ---
        giveaway_embed = discord.Embed(
            title=f"🎁 {name} 🎁", # Changed title to prize name
            description=f"Click the {GIVEAWAY_EMOJI} reaction to enter!\n"
                        f"**Hosted by:** {interaction.user.mention}",
            color=embed_color,
            timestamp=end_time
        )
        giveaway_embed.add_field(name="✨ Winners", value=f"{winners}", inline=True)
        giveaway_embed.add_field(name="⏰ Ends In", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)

        if required_role:
            giveaway_embed.add_field(name="🔑 Required Role", value=required_role.mention, inline=False)
        
        if extra_entry_role:
            giveaway_embed.add_field(
                name="🚀 Extra Entries",
                value=f"Members with {extra_entry_role.mention} get **{extra_entries_for_role} entries**!",
                inline=False
            )
            
        if image_url:
            # Set image with a fixed size if possible by discord API (via thumbnail)
            # Discord embed images typically scale, so setting a fixed size is best done via resizing the actual image file.
            # However, you can use thumbnail for better control over display size.
            giveaway_embed.set_image(url=image_url) # Will scale to fit, Discord doesn't support fixed px for embed images directly
            # You could use .set_thumbnail(url=image_url) if you prefer a smaller, fixed-size image in a corner

        giveaway_embed.set_footer(text=f"Giveaway ID: {datetime.utcnow().timestamp()}") # Unique ID for tracking

        # --- Create View with "See Participants" Button ---
        class GiveawayActionsView(discord.ui.View):
            def __init__(self, giveaway_message_id: str, original_interaction: discord.Interaction):
                super().__init__(timeout=None) # Timeout is handled by the giveaway ending
                self.giveaway_message_id = giveaway_message_id
                self.original_interaction = original_interaction
                self.add_item(discord.ui.Button(label="See Participants", style=discord.ButtonStyle.secondary, emoji="👥", custom_id=f"see_participants_{giveaway_message_id}"))

            @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.primary, emoji=GIVEAWAY_EMOJI, custom_id=f"join_giveaway_{giveaway_message_id}", row=0)
            async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                # This button is primarily for visual guidance. The actual entry is by reaction.
                await interaction.response.send_message("To enter the giveaway, please react to the message with the 🎉 emoji!", ephemeral=True)


        view = ConfirmGiveawayView(interaction)
        confirmation_message_content = "Here's a **preview** of your giveaway. Please review and click 'Start Giveaway' to launch, or 'Cancel' to abort:"
        try:
            await interaction.followup.send(
                content=confirmation_message_content,
                embed=giveaway_embed,
                view=view,
                ephemeral=True
            )
            await view.wait()
        except Exception as e:
            print(f"Error during giveaway confirmation message or waiting for view: {e}")
            return await interaction.followup.send(f"❌ An error occurred during confirmation: {e}", ephemeral=True)

        # --- Process Confirmation Result ---
        if view.confirmed:
            try:
                # The actual giveaway message now has the "See Participants" button
                giveaway_message = await interaction.channel.send(embed=giveaway_embed, view=GiveawayActionsView(f"{datetime.utcnow().timestamp()}", interaction))
                await giveaway_message.add_reaction(GIVEAWAY_EMOJI) # Still use reaction for entry

            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I don't have permissions to send messages or add reactions in this channel. "
                    "Giveaway cancelled. Please check my permissions.", ephemeral=True
                )
                return
            except Exception as e:
                print(f"Error sending actual giveaway message: {e}")
                await interaction.followup.send(f"❌ An error occurred while launching the giveaway: {e}. Giveaway cancelled.", ephemeral=True)
                return

            giveaway_data = {
                "_id": str(giveaway_message.id), # Store the message ID for direct access
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

            await interaction.followup.send(f"✅ Giveaway for **{name}** has been launched in {interaction.channel.mention}!", ephemeral=True)

        else:
            pass

    # --- NEW: Interaction listener for the "See Participants" button ---
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id and custom_id.startswith("see_participants_"):
                giveaway_message_id = custom_id.split("_")[2]

                await interaction.response.defer(ephemeral=True) # Defer to prevent "Interaction failed"

                giveaway_data = self.giveaway_db.find_one({"_id": giveaway_message_id})

                if not giveaway_data:
                    await interaction.followup.send("❌ This giveaway no longer exists or is not in the database.", ephemeral=True)
                    return

                channel = self.bot.get_channel(int(giveaway_data["channel_id"]))
                if not channel:
                    await interaction.followup.send("❌ Could not find the channel for this giveaway.", ephemeral=True)
                    return

                try:
                    giveaway_message = await channel.fetch_message(int(giveaway_message_id))
                except discord.NotFound:
                    await interaction.followup.send("❌ The giveaway message could not be found.", ephemeral=True)
                    return
                except discord.Forbidden:
                    await interaction.followup.send("❌ I don't have permissions to access the giveaway message.", ephemeral=True)
                    return

                all_reactors = []
                for reaction in giveaway_message.reactions:
                    if str(reaction.emoji) == GIVEAWAY_EMOJI:
                        # Fetch users who reacted to the specific message with the giveaway emoji
                        async for user in reaction.users():
                            if not user.bot:
                                all_reactors.append(user)
                        break

                final_participant_list = []
                required_role_id = giveaway_data.get("required_role_id")
                extra_entry_role_id = giveaway_data.get("extra_entry_role_id")
                extra_entries_multiplier = giveaway_data.get("extra_entries_for_role", 1)

                guild = self.bot.get_guild(int(giveaway_data["guild_id"]))
                required_role_obj = guild.get_role(int(required_role_id)) if required_role_id and guild else None
                extra_entry_role_obj = guild.get_role(int(extra_entry_role_id)) if extra_entry_role_id and guild else None

                for participant_user in all_reactors:
                    member = guild.get_member(participant_user.id)
                    if not member:
                        continue # User might have left the guild

                    if required_role_obj and required_role_obj not in member.roles:
                        continue # User does not have the required role

                    final_participant_list.append(member) # Add base entry

                    if extra_entry_role_obj and extra_entry_role_obj in member.roles:
                        for _ in range(extra_entries_multiplier - 1): # Add extra entries
                            final_participant_list.append(member)

                # Use the new ParticipantsView to display paginated list
                view = ParticipantsView(final_participant_list, interaction)
                await view.send_page(interaction) # Send the first page

    # --- Error Handler for the giveaway command ---
    @giveaway.error
    async def giveaway_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            permissions_needed = [p.replace('_', ' ').title() for p in error.missing_permissions]
            await interaction.response.send_message(
                f"❌ You don't have the required permissions to use this command. "
                f"You need the following permission(s): **{', '.join(permissions_needed)}**.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"An unexpected error occurred while processing the command: {error}",
                ephemeral=True
            )

    # --- Background task to check for ended giveaways (Bug Fix & UI Update) ---
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
                    # Don't mark as ended here, as we might regain permissions. The loop will retry.
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
                extra_entries_multiplier = giveaway_data.get("extra_entries_for_role", 1)

                required_role_obj = guild.get_role(int(required_role_id)) if required_role_id else None
                extra_entry_role_obj = guild.get_role(int(extra_entry_role_id)) if extra_entry_role_id else None

                # Check if roles exist before sending warnings
                if required_role_id and not required_role_obj:
                    # Only send if the role was actually set for the giveaway
                    await channel.send(f"⚠️ Warning: The `required_role` for giveaway **'{giveaway_data['giveaway_name']}'** no longer exists. All participants were considered for the base entry.")
                if extra_entry_role_id and not extra_entry_role_obj:
                    # Only send if the role was actually set for the giveaway
                    await channel.send(f"⚠️ Warning: The `extra_entry_role` for giveaway **'{giveaway_data['giveaway_name']}'** no longer exists. Extra entries for this role will be ignored.")

                for participant_user in all_reactors:
                    member = guild.get_member(participant_user.id)
                    if not member:
                        # User might have left the guild, skip them
                        continue

                    # Apply required role filter only if the role exists
                    if required_role_obj and required_role_obj not in member.roles:
                        continue

                    final_participant_list.append(member)

                    # Apply extra entries only if the role exists
                    if extra_entry_role_obj and extra_entry_role_obj in member.roles:
                        for _ in range(extra_entries_multiplier - 1):
                            final_participant_list.append(member)


                winners = []
                # BUG FIX: Ensure unique winners are picked even with extra entries
                eligible_unique_participants = list(set(final_participant_list)) # Get unique members first

                if len(eligible_unique_participants) >= giveaway_data["winner_count"]:
                    winners = random.sample(eligible_unique_participants, giveaway_data["winner_count"])
                else:
                    winners = eligible_unique_participants # If not enough unique participants, all become winners

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
                
                # Update the original embed to reflect the end state and clean up
                original_embed = giveaway_message.embeds[0] if giveaway_message.embeds else discord.Embed()
                original_embed.title = f"🎁 {giveaway_data['giveaway_name']} - Ended 🎁" # Use prize name in ended title
                original_embed.description = f"This giveaway has ended. The winner(s) have been announced!"
                original_embed.color = discord.Color.dark_grey()
                original_embed.set_footer(text=f"Giveaway ended at")
                original_embed.timestamp = datetime.utcnow()
                
                # Clear all fields to keep it clean and only show relevant info
                original_embed.clear_fields()
                original_embed.add_field(name="✨ Winners", value=f"{giveaway_data['winner_count']}", inline=True)
                if winners:
                    original_embed.add_field(name="🏆 Winner(s)", value=winner_mentions, inline=False)
                else:
                    original_embed.add_field(name="😔 No Winners", value="No eligible participants.", inline=False)

                # Remove the "See Participants" button and any other original buttons
                await giveaway_message.edit(embed=original_embed, view=None)

                self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})

            except Exception as e:
                print(f"Error processing giveaway {giveaway_data['_id']}: {e}")
                self.giveaway_db.update_one({"_id": giveaway_data["_id"]}, {"$set": {"is_ended": True}})


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
