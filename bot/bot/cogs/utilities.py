
import asyncio
import discord

from datetime import datetime, timedelta, timezone
from discord import app_commands
from discord.ext import commands, tasks

from bot.services.database import db


class PollView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=86400)
        self.votes = {}
        self.options = options

        for index, option in enumerate(options):
            button = discord.ui.Button(
                label=option[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"knoxbot:poll:{index}"
            )
            button.callback = self.create_callback(index)
            self.add_item(button)

    def create_callback(self, index):
        async def callback(interaction):
            self.votes[interaction.user.id] = index

            counts = [
                sum(1 for vote in self.votes.values() if vote == i)
                for i in range(len(self.options))
            ]

            results = "\n".join(
                f"**{option}:** {counts[i]} vote(s)"
                for i, option in enumerate(self.options)
            )

            await interaction.response.send_message(
                f"Your vote has been recorded.\n\n{results}",
                ephemeral=True
            )

        return callback


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_check.start()

    def cog_unload(self):
        self.reminder_check.cancel()

    @app_commands.command(
        name="serverinfo",
        description="Display information about this server."
    )
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=guild.name,
            colour=discord.Colour.blurple()
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Server ID", value=str(guild.id))
        embed.add_field(name="Members", value=str(guild.member_count))
        embed.add_field(name="Owner", value=str(guild.owner or "Unknown"))
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "D"))

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="userinfo",
        description="Display information about a server member."
    )
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user

        embed = discord.Embed(
            title=f"User information: {member}",
            colour=discord.Colour.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User ID", value=str(member.id))
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "D"))
        embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "D") if member.joined_at else "Unknown")
        embed.add_field(name="Top role", value=member.top_role.mention)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="avatar",
        description="Display a member's avatar."
    )
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            colour=discord.Colour.blurple()
        )
        embed.set_image(url=member.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="poll",
        description="Create a poll with up to five choices."
    )
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Optional third option",
        option4="Optional fourth option",
        option5="Optional fifth option"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: app_commands.Range[str, 1, 200],
        option1: app_commands.Range[str, 1, 80],
        option2: app_commands.Range[str, 1, 80],
        option3: app_commands.Range[str, 1, 80] = None,
        option4: app_commands.Range[str, 1, 80] = None,
        option5: app_commands.Range[str, 1, 80] = None
    ):
        options = [
            option for option in
            [option1, option2, option3, option4, option5]
            if option
        ]

        embed = discord.Embed(
            title=question,
            description="Vote using the buttons below.",
            colour=discord.Colour.blurple()
        )

        await interaction.channel.send(
            embed=embed,
            view=PollView(options)
        )

        await interaction.response.send_message(
            "Poll created.",
            ephemeral=True
        )

    @app_commands.command(
        name="remindme",
        description="Set a reminder in minutes."
    )
    async def remindme(
        self,
        interaction: discord.Interaction,
        minutes: app_commands.Range[int, 1, 10080],
        message: app_commands.Range[str, 1, 500]
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "Use this command in a server.",
                ephemeral=True
            )
            return

        due_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)

        try:
            await asyncio.to_thread(
                lambda: db.table("reminders").insert({
                    "guild_id": str(interaction.guild.id),
                    "user_id": str(interaction.user.id),
                    "message": message,
                    "due_at": due_at.isoformat()
                }).execute()
            )

            await interaction.response.send_message(
                f"Reminder saved for <t:{int(due_at.timestamp())}:R>.",
                ephemeral=True
            )

        except Exception:
            await interaction.response.send_message(
                "Couldn't save your reminder.",
                ephemeral=True
            )

    @tasks.loop(seconds=30)
    async def reminder_check(self):
        try:
            now = datetime.now(timezone.utc).isoformat()

            result = await asyncio.to_thread(
                lambda: db.table("reminders")
                .select("*")
                .eq("completed", False)
                .lte("due_at", now)
                .limit(50)
                .execute()
            )

            for reminder in result.data or []:
                guild = self.bot.get_guild(int(reminder["guild_id"]))
                user_id = int(reminder["user_id"])

                if guild:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await user.send(
                            f"⏰ **KnoxBot Reminder**\n{reminder['message']}"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                await asyncio.to_thread(
                    lambda rid=reminder["id"]: db.table("reminders")
                    .update({"completed": True})
                    .eq("id", rid)
                    .execute()
                )

        except Exception:
            import logging
            logging.getLogger("KnoxBot.Reminders").exception(
                "Reminder processing failed."
            )

    @reminder_check.before_loop
    async def before_reminder_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Utilities(bot))
