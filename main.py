import os
import time
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("discord_bot")

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            description="A general-purpose Discord bot",
        )

        async def setup_hook(self):
        cogs = ["cogs.moderation", "cogs.fun", "cogs.utility", "cogs.protection"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Đồng bộ Slash Commands toàn cầu
        await self.tree.sync()
        logger.info("Slash commands synced globally")

        # Clear guild-specific commands (removes duplicates from previous guild syncs)
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Cleared guild commands for: {guild.name} ({guild.id})")
            except Exception as e:
                logger.warning(f"Could not clear guild commands for {guild.id}: {e}")

        # Sync all commands globally
        await self.tree.sync()
        logger.info("Slash commands synced globally")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{PREFIX}help | Use slash commands!",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", delete_after=5)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have permission to do that.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`", delete_after=5)
        elif isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Bad argument: {error}", delete_after=5)
        else:
            logger.error(f"Unhandled error in command: {error}")


def main():
    if not TOKEN:
        logger.error("DISCORD_TOKEN is not set. Please add it as a secret.")
        raise SystemExit(1)

    backoff = 5
    while True:
        try:
            # Create a fresh bot instance each attempt (fresh event loop via bot.run)
            bot = DiscordBot()
            bot.run(TOKEN, log_handler=None, reconnect=True)
            break  # Clean exit
        except discord.errors.HTTPException as e:
            if e.status == 429:
                logger.warning(f"Rate limited by Discord. Retrying in {backoff}s...")
            else:
                logger.error(f"HTTP error {e.status}: {e.text}. Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        except KeyboardInterrupt:
            logger.info("Shutting down.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)


if __name__ == "__main__":
    main()
              
