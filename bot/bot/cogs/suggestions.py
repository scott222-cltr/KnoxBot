
import asyncio
import discord

from discord import app_commands
from discord.ext import commands

from bot.services.database import db
from bot.services.logging_service import LoggingService


class SuggestionReviewView(discord.ui.View):
    def __init__(self, cog, suggestion_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.suggestion_id = suggestion_id

    async def update_status(self, interaction, status):
        if not interaction.guild:
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Couldn't verify your permissions.",
                ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need Manage Server permission to review suggestions.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await asyncio.to_thread(
                lambda: db.table("suggestions").update({
                    "status": status,
                    "moderator_id": str(interaction.user.id)
                }).eq("id", self.suggestion_id)
                  .eq("guild_id", str(interaction.guild.id))
                  .eq("status", "pending")
                  .execute()
            )

            embed = interaction.message.embeds[0]
            embed.colour = (
                discord.Colour.green()
                if status == "approved"
                else discord.Colour.red()
            )
            embed.add_field(
                name="Decision",
                value=f"{status.title()} by {interaction.user.mention}",
                inline=False
            )

            for child in self.children:
                child.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            await interaction.followup.send(
                f"Suggestion marked as **{status}**."
            )

            await self.cog.logger.log(
                interaction.guild,
                "suggestion_reviewed",
                f"Suggestion #{self.suggestion_id} was {status}.",
                actor=interaction.user
            )

        except Exception:
            await interaction.followup.send(
                "Couldn't update this suggestion. Please try again.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="knoxbot:suggestion:approve"
    )
    async def approve(self, interaction, button):
        await self.update_status(interaction, "approved")

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="knoxbot:suggestion:reject"
    )
    async def reject(self, interaction, button):
        await self.update_status(interaction, "rejected")


class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = LoggingService(bot)

    @app_commands.command(
        name="suggest",
        description="Submit a suggestion to the server."
    )
    @app_commands.describe(
        suggestion="Describe your idea or suggestion."
    )
    async def suggest(
        self,
        interaction: discord.Interaction,
        suggestion: app_commands.Range[str, 5, 1500]
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            result = await asyncio.to_thread(
                lambda: db.table("suggestions").insert({
                    "guild_id": str(interaction.guild.id),
                    "user_id": str(interaction.user.id),
                    "message": suggestion,
                    "status": "pending"
                }).execute()
            )

            suggestion_id = result.data[0]["id"]

            settings = await asyncio.to_thread(
                db.get_guild_settings,
                interaction.guild.id
            )

            config = (settings or {}).get("config") or {}
            channel_id = config.get("suggestions_channel_id")

            if not channel_id:
                await interaction.followup.send(
                    "Your suggestion has been saved, but this server hasn't configured a suggestions channel yet.",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(int(channel_id))

            if not isinstance(channel, discord.TextChannel):
                await interaction.followup.send(
                    "The configured suggestions channel could not be found.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Suggestion #{suggestion_id}",
                description=suggestion,
                colour=discord.Colour.blurple()
            )
            embed.set_author(
                name=str(interaction.user),
                icon_url=interaction.user.display_avatar.url
            )
            embed.add_field(
                name="Status",
                value="Pending review",
                inline=False
            )

            await channel.send(
                embed=embed,
                view=SuggestionReviewView(self, suggestion_id)
            )

            await interaction.followup.send(
                "Your suggestion has been submitted successfully!",
                ephemeral=True
            )

        except Exception:
            await interaction.followup.send(
                "Your suggestion couldn't be submitted. Please try again later.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Suggestions(bot))
