
import os
import asyncio
import discord

from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client

# ==========================================
# KNOXBOT
# Public Discord Management Bot
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing Supabase environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True


class KnoxBot(commands.Bot):

    async def setup_hook(self):
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} slash commands.")

        for guild in self.guilds:
            await register_guild(guild)

    async def on_ready(self):
        print("=" * 40)
        print(f"KnoxBot online: {self.user}")
        print(f"Servers connected: {len(self.guilds)}")
        print("=" * 40)

    async def on_guild_join(self, guild):
        await register_guild(guild)

    async def on_guild_remove(self, guild):
        print(f"KnoxBot removed from: {guild.name}")


bot = KnoxBot(
    command_prefix="!",
    intents=intents
)


async def database_call(function):
    return await asyncio.to_thread(function)


async def register_guild(guild):
    try:
        await database_call(
            lambda: supabase.table("guild_settings").upsert(
                {
                    "guild_id": str(guild.id),
                    "guild_name": guild.name
                },
                on_conflict="guild_id"
            ).execute()
        )
        print(f"Registered server: {guild.name}")

    except Exception as error:
        print(f"Database registration error: {error}")


async def save_case(
    interaction,
    member,
    action,
    reason,
    duration=None
):
    guild = interaction.guild

    await register_guild(guild)

    try:
        await database_call(
            lambda: supabase.table("moderation_cases").insert(
                {
                    "guild_id": str(guild.id),
                    "user_id": str(member.id),
                    "moderator_id": str(interaction.user.id),
                    "action": action,
                    "reason": reason,
                    "duration_seconds": duration
                }
            ).execute()
        )
        return True

    except Exception as error:
        print(f"Moderation database error: {error}")
        return False


def can_moderate(interaction, member):
    if member.id == interaction.user.id:
        return False, "You cannot moderate yourself."

    if member.id == interaction.guild.owner_id:
        return False, "You cannot moderate the server owner."

    if member.id == bot.user.id:
        return False, "You cannot moderate KnoxBot."

    if member.top_role >= interaction.user.top_role:
        return False, "That member has an equal or higher role than you."

    if member.top_role >= interaction.guild.me.top_role:
        return False, "That member has an equal or higher role than KnoxBot."

    return True, None


def moderation_embed(action, member, moderator, reason):
    embed = discord.Embed(
        title=f"KnoxBot | {action}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Member",
        value=f"{member} (`{member.id}`)",
        inline=False
    )

    embed.add_field(
        name="Moderator",
        value=moderator.mention,
        inline=True
    )

    embed.add_field(
        name="Reason",
        value=reason,
        inline=False
    )

    embed.set_footer(text="KnoxBot Moderation System")
    return embed


@bot.tree.command(name="ping", description="Check KnoxBot's response time.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"KnoxBot is online! Latency: **{latency}ms**",
        ephemeral=True
    )


@bot.tree.command(name="ban", description="Ban a member from your server.")
@app_commands.describe(
    member="The member to ban",
    reason="Why this member is being banned"
)
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, member)

    if not allowed:
        return await interaction.response.send_message(
            error, ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        await member.ban(reason=f"{reason} | Moderator: {interaction.user}")

        recorded = await save_case(
            interaction, member, "BAN", reason
        )

        await interaction.followup.send(
            f"Successfully banned **{member}**.\n"
            f"Reason: {reason}\n"
            f"Case recorded: {'Yes' if recorded else 'No'}"
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to ban that member."
        )


@bot.tree.command(name="kick", description="Kick a member from your server.")
@app_commands.describe(
    member="The member to kick",
    reason="Why this member is being kicked"
)
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, member)

    if not allowed:
        return await interaction.response.send_message(
            error, ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        await member.kick(
            reason=f"{reason} | Moderator: {interaction.user}"
        )

        recorded = await save_case(
            interaction, member, "KICK", reason
        )

        await interaction.followup.send(
            f"Successfully kicked **{member}**.\n"
            f"Case recorded: {'Yes' if recorded else 'No'}"
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to kick that member."
        )


@bot.tree.command(name="timeout", description="Timeout a server member.")
@app_commands.describe(
    member="The member to timeout",
    minutes="Timeout duration in minutes (1-40320)",
    reason="Reason for the timeout"
)
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):
    allowed, error = can_moderate(interaction, member)

    if not allowed:
        return await interaction.response.send_message(
            error, ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        duration = minutes * 60

        await member.timeout(
            discord.utils.utcnow() + __import__("datetime").timedelta(minutes=minutes),
            reason=f"{reason} | Moderator: {interaction.user}"
        )

        recorded = await save_case(
            interaction, member, "TIMEOUT", reason, duration
        )

        await interaction.followup.send(
            f"Successfully timed out **{member}** for "
            f"**{minutes} minutes**.\n"
            f"Case recorded: {'Yes' if recorded else 'No'}"
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to timeout that member."
        )


@bot.tree.command(name="warn", description="Issue a formal warning.")
@app_commands.describe(
    member="The member to warn",
    reason="Reason for the warning"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):
    allowed, error = can_moderate(interaction, member)

    if not allowed:
        return await interaction.response.send_message(
            error, ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    recorded = await save_case(
        interaction, member, "WARN", reason
    )

    try:
        await member.send(
            embed=moderation_embed(
                "Official Warning",
                member,
                interaction.user,
                reason
            )
        )
        dm_status = "Member notified by DM."

    except discord.Forbidden:
        dm_status = "Member's DMs are closed."

    await interaction.followup.send(
        f"Warning issued to **{member}**.\n"
        f"{dm_status}\n"
        f"Case recorded: {'Yes' if recorded else 'No'}"
    )


@bot.tree.error
async def command_error(interaction, error):

    if isinstance(error, app_commands.MissingPermissions):
        message = "You don't have permission to use this command."

    elif isinstance(error, app_commands.BotMissingPermissions):
        message = "KnoxBot is missing a required permission."

    else:
        print(f"Command error: {error}")
        message = "An unexpected error occurred."

    if interaction.response.is_done():
        await interaction.followup.send(
            message, ephemeral=True
        )
    else:
        await interaction.response.send_message(
            message, ephemeral=True
        )


bot.run(TOKEN)
