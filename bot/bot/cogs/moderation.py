
import asyncio
import discord

from discord import app_commands
from discord.ext import commands

from bot.security import SecurityService
from bot.services.database import db
from bot.services.logging_service import LoggingService


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.security = SecurityService()
        self.logger = LoggingService(bot)

    async def save_case(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        action: str,
        reason: str
    ):
        try:
            await asyncio.to_thread(
                lambda: db.table("moderation_cases").insert({
                    "guild_id": str(guild_id),
                    "user_id": str(user_id),
                    "moderator_id": str(moderator_id),
                    "action": action,
                    "reason": reason
                }).execute()
            )
        except Exception:
            # Log the failure without exposing database credentials.
            import logging
            logging.getLogger("KnoxBot.Moderation").exception(
                "Failed to save moderation case."
            )

    @app_commands.command(
        name="purge",
        description="Delete a number of recent messages."
    )
    @app_commands.describe(
        amount="Number of messages to delete (1–100)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(
        manage_messages=True,
        read_message_history=True
    )
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100]
    ):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command can only be used in a server text channel.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(
                limit=amount,
                reason=f"Purged by {interaction.user} ({interaction.user.id})"
            )

            await interaction.followup.send(
                f"Deleted **{len(deleted)}** messages.",
                ephemeral=True
            )

            await self.save_case(
                interaction.guild_id,
                interaction.user.id,
                interaction.user.id,
                "purge",
                f"Deleted {len(deleted)} messages in #{interaction.channel.name}"
            )

            await self.logger.log(
                interaction.guild,
                "message_purge",
                f"Deleted {len(deleted)} messages in {interaction.channel.mention}.",
                actor=interaction.user,
                colour=discord.Colour.orange(),
                extra={"deleted_count": len(deleted)}
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "KnoxBot doesn't have permission to delete messages here.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord couldn't delete those messages. Please try again.",
                ephemeral=True
            )

    @app_commands.command(
        name="warnings",
        description="View saved moderation cases for a member."
    )
    @app_commands.describe(
        member="Member whose moderation history you want to view."
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            result = await asyncio.to_thread(
                lambda: db.table("moderation_cases")
                .select("action,reason,moderator_id,created_at")
                .eq("guild_id", str(interaction.guild_id))
                .eq("user_id", str(member.id))
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )

            cases = result.data or []

            if not cases:
                await interaction.followup.send(
                    f"No saved moderation cases were found for {member.mention}.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Moderation history: {member}",
                colour=discord.Colour.orange()
            )

            for case in cases:
                embed.add_field(
                    name=f"{case['action'].title()} — {case.get('created_at', 'Unknown date')}",
                    value=(
                        f"Reason: {case.get('reason') or 'No reason provided'}\n"
                        f"Moderator ID: {case.get('moderator_id', 'Unknown')}"
                    )[:1024],
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception:
            await interaction.followup.send(
                "I couldn't retrieve the moderation history. Check the bot's database connection and table permissions.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Moderation(bot))
