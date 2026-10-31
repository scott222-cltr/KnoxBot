
import discord

from discord.ext import commands
from bot.services.logging_service import LoggingService


class ServerLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = LoggingService(bot)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None or message.author.bot:
            return

        content = message.content or "[No text content]"
        if len(content) > 1500:
            content = content[:1500] + "…"

        await self.logger.log(
            message.guild,
            "message_deleted",
            f"A message by {message.author.mention} was deleted in "
            f"{message.channel.mention}.\n\n**Content:**\n{content}",
            actor=None,
            target=message.author,
            colour=discord.Colour.red(),
            extra={
                "channel_id": message.channel.id,
                "message_id": message.id
            }
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is None or before.author.bot:
            return

        if before.content == after.content:
            return

        old_content = before.content or "[No text content]"
        new_content = after.content or "[No text content]"

        await self.logger.log(
            before.guild,
            "message_edited",
            f"A message by {before.author.mention} was edited in "
            f"{before.channel.mention}.\n\n"
            f"**Before:**\n{old_content[:700]}\n\n"
            f"**After:**\n{new_content[:700]}",
            target=before.author,
            colour=discord.Colour.orange(),
            extra={
                "channel_id": before.channel.id,
                "message_id": before.id
            }
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.guild is None:
            return

        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        if added_roles or removed_roles:
            changes = []

            if added_roles:
                changes.append(
                    "**Added:** " + ", ".join(r.name for r in added_roles)
                )

            if removed_roles:
                changes.append(
                    "**Removed:** " + ", ".join(r.name for r in removed_roles)
                )

            await self.logger.log(
                after.guild,
                "member_roles_updated",
                f"Roles changed for {after.mention}.\n" + "\n".join(changes),
                target=after,
                colour=discord.Colour.blurple(),
                extra={
                    "added_role_ids": [r.id for r in added_roles],
                    "removed_role_ids": [r.id for r in removed_roles]
                }
            )

        if before.nick != after.nick:
            await self.logger.log(
                after.guild,
                "nickname_changed",
                f"Nickname changed for {after.mention}: "
                f"`{before.nick or before.name}` → `{after.nick or after.name}`",
                target=after,
                colour=discord.Colour.blurple()
            )

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if channel.guild:
            await self.logger.log(
                channel.guild,
                "channel_created",
                f"Channel created: {channel.mention if hasattr(channel, 'mention') else channel.name}",
                colour=discord.Colour.green(),
                extra={"channel_id": channel.id}
            )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if channel.guild:
            await self.logger.log(
                channel.guild,
                "channel_deleted",
                f"Channel deleted: **{channel.name}**",
                colour=discord.Colour.red(),
                extra={"channel_id": channel.id}
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return

        if after.channel and not before.channel:
            description = f"{member.mention} joined voice channel **{after.channel.name}**."
        elif before.channel and not after.channel:
            description = f"{member.mention} left voice channel **{before.channel.name}**."
        else:
            description = (
                f"{member.mention} moved from **{before.channel.name}** "
                f"to **{after.channel.name}**."
            )

        await self.logger.log(
            member.guild,
            "voice_activity",
            description,
            target=member,
            colour=discord.Colour.blurple()
        )


async def setup(bot):
    await bot.add_cog(ServerLogging(bot))
