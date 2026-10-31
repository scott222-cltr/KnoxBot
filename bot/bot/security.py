
import discord


class SecurityService:

    @staticmethod
    def is_staff(member: discord.Member) -> bool:
        """Check whether a member has moderation permissions."""
        return (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or member.guild_permissions.moderate_members
            or member.guild_permissions.kick_members
            or member.guild_permissions.ban_members
        )

    @staticmethod
    def can_moderate(
        moderator: discord.Member,
        target: discord.Member,
        bot_member: discord.Member
    ) -> tuple[bool, str]:

        if moderator.id == target.id:
            return False, "You cannot moderate yourself."

        if target.id == moderator.guild.owner_id:
            return False, "You cannot moderate the server owner."

        if target.id == bot_member.id:
            return False, "You cannot moderate KnoxBot."

        if moderator.id != moderator.guild.owner_id:
            if target.top_role >= moderator.top_role:
                return False, "You cannot moderate someone with an equal or higher role."

        if target.top_role >= bot_member.top_role:
            return False, "KnoxBot's role must be above the target's highest role."

        return True, "Permission check passed."

    @staticmethod
    def can_manage_roles(
        moderator: discord.Member,
        target_role: discord.Role,
        bot_member: discord.Member
    ) -> tuple[bool, str]:

        if not moderator.guild_permissions.manage_roles:
            return False, "You need Manage Roles permission."

        if target_role.is_default():
            return False, "The @everyone role cannot be managed."

        if target_role.managed:
            return False, "Integration-managed roles cannot be changed."

        if moderator.id != moderator.guild.owner_id:
            if target_role >= moderator.top_role:
                return False, "That role is equal to or above your highest role."

        if target_role >= bot_member.top_role:
            return False, "KnoxBot's role must be above the role being managed."

        return True, "Permission check passed."
