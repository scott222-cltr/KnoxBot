
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)

@bot.event
async def on_ready():
    print(f"KnoxBot is online as {bot.user}")
    print(f"Connected to {len(bot.guilds)} servers.")

@bot.command()
@commands.has_permissions(administrator=True)
async def ping(ctx):
    await ctx.send(f"KnoxBot is online! Latency: {round(bot.latency * 1000)}ms")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing!")

bot.run(TOKEN)
