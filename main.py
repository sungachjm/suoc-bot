import os
import logging
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── Load Environment Variables ────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Setup Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("discord_bot.main")

# ── Keep Alive Web Server (Flask) ─────────────────────────────────────────────
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ── Bot Class Setup ───────────────────────────────────────────────────────────
class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        cogs = ["cogs.moderation", "cogs.fun", "cogs.utility", "cogs.protection"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")

        # Sync slash commands globally
        await self.tree.sync()
        logger.info("Slash commands synced globally")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Bot is ready and running!")

# ── Entry Point ───────────────────────────────────────────────────────────────
async def main():
    if not TOKEN:
        logger.error("No DISCORD_TOKEN found in environment variables!")
        return

    keep_alive()
    bot = DiscordBot()
    
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
    
