
import asyncio
import re
import time
import discord

from discord import app_commands
from discord.ext import commands

from bot.services.database import db
from bot.services.logging_service import LoggingService


class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = LoggingService(bot)
        self.cache = {}
        self.last_refresh = {}

    async def get_responses(self, guild_id):
        now = time.monotonic()

        if (
            guild_id in self.cache
            and now - self.last_refresh.get(guild_id, 0) < 60
        ):
            return self.cache[guild_id]

        try:
            result = await asyncio.to_thread(
                lambda: db.table("auto_responses")
                .select("*")
                .eq("guild_id", str(guild_id))
                .eq("enabled", True)
                .execute()
            )

            self.cache[guild_id] = result.data or []
            self.last_refresh[guild_id] = now

            return self.cache[guild_id]

        except Exception:
            return []

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return

        responses = await self.get_responses(message.guild.id)
        content = message.content.casefold()

        for response in responses:
            trigger = response.get("trigger_text", "").casefold().strip()

            if not trigger:
                continue

            if trigger in content:
                try:
                    await message.channel.send(
                        response["response_text"][:2000],
                        allowed_mentions=discord.AllowedMentions.none()
                    )
                except discord.HTTPException:
                    pass

                break

    @app_commands.command(
        name="addresponse",
        description="Add an automatic response trigger."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addresponse(
        self,
        interaction: discord.Interaction,
        trigger: app_commands.Range[str, 1, 100],
        response: app_commands.Range[str, 1, 1500]
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True
            )
            return

        try:
            await asyncio.to_thread(
                lambda: db.table("auto_responses").insert({
                    "guild_id": str(interaction.guild.id),
                    "trigger_text": trigger.strip(),
                    "response_text": response.strip(),
                    "enabled": True
                }).execute()
            )

            self.cache.pop(interaction.guild.id, None)

            await interaction.response.send_message(
                f"Automatic response created for **{trigger}**.",
                ephemeral=True
            )

        except Exception:
            await interaction.response.send_message(
                "Couldn't save that automatic response.",
                ephemeral=True
            )

    @app_commands.command(
        name="responses",
        description="View configured automatic responses."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def responses(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True
            )
            return

        entries = await self.get_responses(interaction.guild.id)

        if not entries:
            await interaction.response.send_message(
                "There are no active automatic responses.",
                ephemeral=True
            )
            return

        description = "\n".join(
            f"**{entry['trigger_text']}** → {entry['response_text'][:100]}"
            for entry in entries[:15]
        )

        embed = discord.Embed(
            title="Automatic Responses",
            description=description,
            colour=discord.Colour.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
