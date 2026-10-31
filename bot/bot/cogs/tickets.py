
import asyncio
import discord

from discord import app_commands
from discord.ext import commands

from bot.services.database import db


class TicketControls(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.primary,
        custom_id="knoxbot:ticket:claim",
        emoji="🙋"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used in a server.",
                ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "You need Manage Channels permission to claim tickets.",
                ephemeral=True
            )
            return

        try:
            await asyncio.to_thread(
                lambda: db.table("tickets").update({
                    "claimed_by": str(interaction.user.id)
                }).eq("guild_id", str(interaction.guild.id))
                  .eq("channel_id", str(interaction.channel_id))
                  .eq("status", "open")
                  .execute()
            )

            await interaction.response.send_message(
                f"This ticket has been claimed by {interaction.user.mention}."
            )
        except Exception:
            await interaction.response.send_message(
                "I couldn't save the claim. Please try again later.",
                ephemeral=True
            )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="knoxbot:ticket:close",
        emoji="🔒"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "This button can only be used in a ticket text channel.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Couldn't verify your server permissions.",
                ephemeral=True
            )
            return

        if not (
            interaction.user.guild_permissions.manage_channels
            or interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                "You need Manage Channels or Manage Server permission to close tickets.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await asyncio.to_thread(
                lambda: db.table("tickets").update({
                    "status": "closed",
                    "closed_at": "now()"
                }).eq("guild_id", str(interaction.guild.id))
                  .eq("channel_id", str(interaction.channel.id))
                  .eq("status", "open")
                  .execute()
            )

            await interaction.followup.send(
                "Ticket closed. This channel will be deleted in 5 seconds.",
                ephemeral=True
            )

            await asyncio.sleep(5)
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

        except Exception:
            await interaction.followup.send(
                "I couldn't close this ticket. Check the bot's permissions and database.",
                ephemeral=True
            )


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_view = TicketControls(self)

    async def cog_load(self):
        self.bot.add_view(self.ticket_view)

    @app_commands.command(
        name="ticketpanel",
        description="Post a button for members to open support tickets."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Use this command in a server text channel.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="KnoxBot Support",
            description=(
                "Need help? Click **Open Ticket** below to create a private "
                "support channel."
            ),
            colour=discord.Colour.blurple()
        )

        view = TicketOpenView(self)
        await interaction.channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            "Ticket panel posted.",
            ephemeral=True
        )


class TicketOpenView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.success,
        custom_id="knoxbot:ticket:open",
        emoji="🎫"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button can only be used in a server.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            existing = await asyncio.to_thread(
                lambda: db.table("tickets")
                .select("id,channel_id")
                .eq("guild_id", str(guild.id))
                .eq("opener_id", str(interaction.user.id))
                .eq("status", "open")
                .limit(1)
                .execute()
            )

            if existing.data:
                channel_id = existing.data[0].get("channel_id")
                channel = guild.get_channel(int(channel_id)) if channel_id else None

                if channel:
                    await interaction.followup.send(
                        f"You already have an open ticket: {channel.mention}",
                        ephemeral=True
                    )
                    return

            category = discord.utils.get(guild.categories, name="Tickets")

            if category is None:
                category = await guild.create_category(
                    "Tickets",
                    reason="KnoxBot ticket setup"
                )

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )
            }

            if guild.me:
                overwrites[guild.me] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )

            channel = await guild.create_text_channel(
                f"ticket-{interaction.user.name}".lower()[:90],
                category=category,
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}"
            )

            number_result = await asyncio.to_thread(
                lambda: db.table("tickets")
                .select("ticket_number")
                .eq("guild_id", str(guild.id))
                .order("ticket_number", desc=True)
                .limit(1)
                .execute()
            )

            ticket_number = (
                int(number_result.data[0]["ticket_number"]) + 1
                if number_result.data else 1
            )

            await asyncio.to_thread(
                lambda: db.table("tickets").insert({
                    "guild_id": str(guild.id),
                    "ticket_number": ticket_number,
                    "channel_id": str(channel.id),
                    "opener_id": str(interaction.user.id),
                    "status": "open",
                    "subject": "Support ticket"
                }).execute()
            )

            embed = discord.Embed(
                title=f"Support Ticket #{ticket_number}",
                description=(
                    f"Hello {interaction.user.mention}!\n\n"
                    "Please describe what you need help with. A member of "
                    "the server team will assist you."
                ),
                colour=discord.Colour.blurple()
            )

            await channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=self.cog.ticket_view
            )

            await interaction.followup.send(
                f"Your ticket has been created: {channel.mention}",
                ephemeral=True
            )

        except Exception:
            await interaction.followup.send(
                "I couldn't create your ticket. Check KnoxBot's channel permissions and database connection.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
