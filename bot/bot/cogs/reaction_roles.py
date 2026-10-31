
import discord

from discord import app_commands
from discord.ext import commands

from bot.services.database import db


class ReactionRoleView(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = int(role_id)

    @discord.ui.button(
        label="Get Role",
        style=discord.ButtonStyle.primary,
        custom_id="knoxbot:reaction_role:get"
    )
    async def get_role(self, interaction, button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This button only works in a server.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(self.role_id)

        if role is None:
            await interaction.response.send_message(
                "That role no longer exists.",
                ephemeral=True
            )
            return

        bot_member = interaction.guild.me

        if bot_member is None or role >= bot_member.top_role:
            await interaction.response.send_message(
                "KnoxBot cannot manage that role. Please check its role hierarchy.",
                ephemeral=True
            )
            return

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(
                    role,
                    reason="KnoxBot self-role removal"
                )
                message = f"The **{role.name}** role has been removed."
            else:
                await interaction.user.add_roles(
                    role,
                    reason="KnoxBot self-role assignment"
                )
                message = f"You have received the **{role.name}** role."

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "KnoxBot doesn't have permission to manage that role.",
                ephemeral=True
            )


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="reactionrole",
        description="Create a button that gives members a role."
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        label: app_commands.Range[str, 1, 50]
    ):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "Use this command in a server text channel.",
                ephemeral=True
            )
            return

        bot_member = interaction.guild.me

        if bot_member is None or role >= bot_member.top_role:
            await interaction.response.send_message(
                "Move KnoxBot's role above the selected role first.",
                ephemeral=True
            )
            return

        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "That role cannot be used for self-assignment.",
                ephemeral=True
            )
            return

        try:
            view = ReactionRoleView(role.id)
            view.children[0].label = label

            embed = discord.Embed(
                title="Choose Your Role",
                description=f"Click the button below to receive **{role.name}**.",
                colour=discord.Colour.blurple()
            )

            message = await interaction.channel.send(
                embed=embed,
                view=view
            )

            await db.table("reaction_roles").insert({
                "guild_id": str(interaction.guild.id),
                "channel_id": str(interaction.channel.id),
                "message_id": str(message.id),
                "emoji": "button",
                "role_id": str(role.id)
            }).execute()

            await interaction.response.send_message(
                "Reaction-role button created successfully.",
                ephemeral=True
            )

        except Exception:
            await interaction.response.send_message(
                "Couldn't create the role button. Check database access and bot permissions.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
