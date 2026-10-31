
import asyncio
import random
import time
import discord

from discord import app_commands
from discord.ext import commands

from bot.services.database import db


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @staticmethod
    def xp_required(level):
        return 100 * (level + 1) ** 2

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()

        if now - self.cooldowns.get(key, 0) < 60:
            return

        self.cooldowns[key] = now

        gained_xp = random.randint(15, 25)

        try:
            result = await asyncio.to_thread(
                lambda: db.table("member_levels")
                .select("*")
                .eq("guild_id", str(message.guild.id))
                .eq("user_id", str(message.author.id))
                .limit(1)
                .execute()
            )

            if result.data:
                record = result.data[0]
                total_xp = int(record["xp"]) + gained_xp
                level = int(record["level"])
                required = self.xp_required(level)

                while total_xp >= required:
                    total_xp -= required
                    level += 1
                    required = self.xp_required(level)

                await asyncio.to_thread(
                    lambda: db.table("member_levels").update({
                        "xp": total_xp,
                        "level": level,
                        "last_xp_at": discord.utils.utcnow().isoformat()
                    }).eq("guild_id", str(message.guild.id))
                      .eq("user_id", str(message.author.id))
                      .execute()
                )

            else:
                total_xp = gained_xp
                level = 0

                await asyncio.to_thread(
                    lambda: db.table("member_levels").insert({
                        "guild_id": str(message.guild.id),
                        "user_id": str(message.author.id),
                        "xp": total_xp,
                        "level": level,
                        "last_xp_at": discord.utils.utcnow().isoformat()
                    }).execute()
                )

        except Exception:
            import logging
            logging.getLogger("KnoxBot.Levels").exception(
                "Could not update member XP."
            )

    @app_commands.command(
        name="rank",
        description="View your XP and current level."
    )
    async def rank(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True
            )
            return

        member = member or interaction.user

        try:
            result = await asyncio.to_thread(
                lambda: db.table("member_levels")
                .select("*")
                .eq("guild_id", str(interaction.guild.id))
                .eq("user_id", str(member.id))
                .limit(1)
                .execute()
            )

            if not result.data:
                await interaction.response.send_message(
                    f"{member.display_name} hasn't earned any XP yet.",
                    ephemeral=True
                )
                return

            record = result.data[0]
            level = int(record["level"])
            xp = int(record["xp"])
            required = self.xp_required(level)

            embed = discord.Embed(
                title=f"{member.display_name}'s Rank",
                colour=discord.Colour.blurple()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Level", value=str(level))
            embed.add_field(name="XP", value=f"{xp} / {required}")

            await interaction.response.send_message(embed=embed)

        except Exception:
            await interaction.response.send_message(
                "Couldn't retrieve rank information.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Levels(bot))
