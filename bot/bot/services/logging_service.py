
import discord
import asyncio
import logging

from datetime import datetime, timezone
from bot.services.database import db

logger = logging.getLogger("KnoxBot.Logging")


class LoggingService:

    def __init__(self, bot):
        self.bot = bot

    async def log(
        self,
        guild: discord.Guild,
        event_type: str,
        description: str,
        actor=None,
        target=None,
        colour=discord.Colour.blurple(),
        extra=None
    ):
        if guild is None:
            return

        actor_id = getattr(actor, "id", None)
        target_id = getattr(target, "id", None)

        details = {
            "description": description,
            "actor_name": str(actor) if actor else None,
            "target_name": str(target) if target else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "extra": extra or {}
        }

        # Save the event to Supabase without blocking Discord's event loop.
        try:
            await asyncio.to_thread(
                db.log_event,
                guild.id,
                event_type,
                actor_id,
                target_id,
                details
            )
        except Exception:
            logger.exception("Failed to save event to Supabase.")

        # Read the configured Discord logging channel.
        try:
            settings = await asyncio.to_thread(
                db.get_guild_settings,
                guild.id
            )

            config = (settings or {}).get("config") or {}
            channel_id = config.get("log_channel_id")

            if not channel_id:
                return

            channel = guild.get_channel(int(channel_id))

            if channel is None:
                return

            embed = discord.Embed(
                title=f"KnoxBot | {event_type.replace('_', ' ').title()}",
                description=description,
                colour=colour,
                timestamp=datetime.now(timezone.utc)
            )

            if actor:
                embed.add_field(
                    name="Actor",
                    value=f"{actor.mention}\n`{actor.id}`",
                    inline=True
                )

            if target:
                embed.add_field(
                    name="Target",
                    value=f"{target.mention}\n`{target.id}`",
                    inline=True
                )

            embed.set_footer(text="KnoxBot Logging System")

            await channel.send(embed=embed)

        except (ValueError, discord.Forbidden, discord.HTTPException):
            logger.exception("Could not send Discord log.")
        except Exception:
            logger.exception("Unexpected logging error.")


async def setup_logging(bot):
    bot.logging_service = LoggingService(bot)

