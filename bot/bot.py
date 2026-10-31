
import os
import asyncio
import discord

from datetime import timedelta
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client

# ==========================================
# KNOXBOT
# Public Discord Management Bot
# ==========================================

load_dotenv("/home/container/.env")
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN environment variable")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing Supabase environment variables")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# ==========================================
# DISCORD CONFIGURATION
# ==========================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True


# Only load modules that are ready for initial integration.
# We will add the remaining modules after their outstanding
# persistence and reliability issues have been fixed.

EXTENSIONS = [
    "knoxbot.cogs.welcome",
    "knoxbot.cogs.moderation",
    "knoxbot.cogs.logging",
    "knoxbot.cogs.automod",
]


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

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

    if guild is None:
        return False

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


# ==========================================
# MODERATION SECURITY
# ==========================================

def can_moderate(interaction, member):
    guild = interaction.guild
    moderator = interaction.user
    bot_member = guild.me

    if member.id == moderator.id:
        return False, "You cannot moderate yourself."

    if member.id == guild.owner_id:
        return False, "You cannot moderate the server owner."

    if bot.user and member.id == bot.user.id:
        return False, "You cannot moderate KnoxBot."

    if (
        moderator.id != guild.owner_id
        and member.top_role >= moderator.top_role
    ):
        return False, "That member has an equal or higher role than you."

    if bot_member and member.top_role >= bot_member.top_role:
        return False, "That member has an equal or higher role than KnoxBot."

    return True, None


# ==========================================
# MODERATION EMBEDS
# ==========================================

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


# ==========================================
# BOT CLASS
# ==========================================

class KnoxBot(commands.Bot):

    async def setup_hook(self):

        print("Loading KnoxBot modules...")

        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                print(f"[LOADED] {extension}")

            except Exception as error:
                print(f"[FAILED] {extension}: {error}")

        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global slash commands.")

        except Exception as error:
            print(f"Slash command sync failed: {error}")

    async def on_ready(self):
        print("=" * 45)
        print(f"KnoxBot online: {self.user}")
        print(f"Servers connected: {len(self.guilds)}")
        print("=" * 45)

        for guild in self.guilds:
            await register_guild(guild)

    async def on_guild_join(self, guild):
        print(f"KnoxBot joined: {guild.name}")
        await register_guild(guild)

    async def on_guild_remove(self, guild):
        print(f"KnoxBot removed from: {guild.name}")


bot = KnoxBot(
    command_prefix="!",
    intents=intents
)


# ==========================================
# PING COMMAND
# ==========================================

@bot.tree.command(
    name="ping",
    description="Check KnoxBot's response time."
)
async def ping(interaction: discord.Interaction):

    latency = round(bot.latency * 1000)

    await interaction.response.send_message(
        f"KnoxBot is online! Latency: **{latency}ms**",
        ephemeral=True
    )


# ==========================================
# BAN COMMAND
# ==========================================

@bot.tree.command(
    name="ban",
    description="Ban a member from your server."
)
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
            error,
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        await member.ban(
            reason=f"{reason} | Moderator: {interaction.user}"
        )

        recorded = await save_case(
            interaction,
            member,
            "BAN",
            reason
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


# ==========================================
# KICK COMMAND
# ==========================================

@bot.tree.command(
    name="kick",
    description="Kick a member from your server."
)
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
            error,
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        await member.kick(
            reason=f"{reason} | Moderator: {interaction.user}"
        )

        recorded = await save_case(
            interaction,
            member,
            "KICK",
            reason
        )

        await interaction.followup.send(
            f"Successfully kicked **{member}**.\n"
            f"Case recorded: {'Yes' if recorded else 'No'}"
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to kick that member."
        )


# ==========================================
# TIMEOUT COMMAND
# ==========================================

@bot.tree.command(
    name="timeout",
    description="Timeout a server member."
)
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
            error,
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    try:
        duration = minutes * 60

        await member.timeout(
            discord.utils.utcnow() + timedelta(minutes=minutes),
            reason=f"{reason} | Moderator: {interaction.user}"
        )

        recorded = await save_case(
            interaction,
            member,
            "TIMEOUT",
            reason,
            duration
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


# ==========================================
# WARN COMMAND
# ==========================================

@bot.tree.command(
    name="warn",
    description="Issue a formal warning."
)
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
            error,
            ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    recorded = await save_case(
        interaction,
        member,
        "WARN",
        reason
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


# ==========================================
# COMMAND ERROR HANDLING
# ==========================================

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
            message,
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True
        )


# ==========================================
# START KNOXBOT
# ==========================================

bot.run(TOKEN)
