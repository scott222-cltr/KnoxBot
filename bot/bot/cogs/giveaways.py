
import asyncio
import random
import discord

from datetime import datetime, timedelta, timezone
from discord import app_commands
from discord.ext import commands, tasks

from bot.services.database import db
from bot.services.logging_service import LoggingService


class GiveawayEntryView(discord.ui.View):
    def __init__(self, cog, giveaway_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="Enter Giveaway",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="knoxbot:giveaway:enter"
    )
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Giveaway entry buttons are prepared, but persistent entry storage "
            "must be configured before entries can be accepted.",
            ephemeral=True
        )


class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = LoggingService(bot)

    @app_commands.command(
        name="giveaway",
        description="Start a giveaway in this channel."
    )
    @app_commands.describe(
        prize="What members can win",
        duration_minutes="How long the giveaway lasts, in minutes",
        winners="Number of winners (1–10)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(
        self,
        interaction: discord.Interaction,
        prize: app_commands.Range[str, 1, 150],
        duration_minutes: app_commands.Range[int, 1, 10080],
        winners: app_commands.Range[int, 1, 10] = 1
    ):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Use this command in a server text channel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        ends_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        try:
            result = await asyncio.to_thread(
                lambda: db.table("giveaways").insert({
                    "guild_id": str(interaction.guild.id),
                    "channel_id": str(interaction.channel.id),
                    "prize": prize,
                    "winner_count": winners,
                    "ends_at": ends_at.isoformat(),
                    "status": "active",
                    "created_by": str(interaction.user.id)
                }).execute()
            )

            giveaway_id = result.data[0]["id"]

            embed = discord.Embed(
                title="🎉 Giveaway!",
                description=(
                    f"**Prize:** {prize}\n"
                    f"**Winners:** {winners}\n"
                    f"**Ends:** <t:{int(ends_at.timestamp())}:R>\n\n"
                    "Press the button below to enter!"
                ),
                colour=discord.Colour.gold()
            )
            embed.set_footer(text=f"KnoxBot Giveaway • ID {giveaway_id}")

            message = await interaction.channel.send(
                embed=embed,
                view=GiveawayEntryView(self, giveaway_id)
            )

            await asyncio.to_thread(
                lambda: db.table("giveaways").update({
                    "message_id": str(message.id)
                }).eq("id", giveaway_id).execute()
            )

            await interaction.followup.send(
                f"Giveaway created for **{prize}**.",
                ephemeral=True
            )

        except Exception:
            await interaction.followup.send(
                "The giveaway couldn't be created. Check the database connection and channel permissions.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
