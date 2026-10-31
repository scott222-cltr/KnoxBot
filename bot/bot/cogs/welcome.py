
import discord
from discord.ext import commands

from bot.services.database import db
from bot.services.logging_service import LoggingService


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = LoggingService(bot)

    async def get_config(self, guild_id: int) -> dict:
        try:
            settings = await __import__("asyncio").to_thread(
                db.get_guild_settings, guild_id
            )
            return (settings or {}).get("config") or {}
        except Exception:
            return {}

    async def send_member_message(self, member, setting_name, default_message):
        config = await self.get_config(member.guild.id)

        channel_id = config.get(f"{setting_name}_channel_id")
        message = config.get(f"{setting_name}_message", default_message)

        if not channel_id:
            return

        channel = member.guild.get_channel(int(channel_id))
        if channel is None:
            return

        formatted = message.format(
            user=member.mention,
            username=member.name,
            server=member.guild.name,
            member_count=member.guild.member_count or 0
        )

        embed = discord.Embed(
            description=formatted,
            colour=discord.Colour.blurple()
        )
        embed.set_author(
            name=str(member),
            icon_url=member.display_avatar.url
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.send_member_message(
            member,
            "welcome",
            "Welcome {user} to **{server}**! You're member #{member_count}."
        )

        await self.logger.log(
            member.guild,
            "member_join",
            f"{member.mention} joined the server.",
            target=member,
            colour=discord.Colour.green()
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.send_member_message(
            member,
            "goodbye",
            "**{username}** has left **{server}**."
        )

        await self.logger.log(
            member.guild,
            "member_leave",
            f"{member} left the server.",
            target=member,
            colour=discord.Colour.orange()
        )


async def setup(bot):
    await bot.add_cog(Welcome(bot))
