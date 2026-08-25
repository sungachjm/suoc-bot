import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger("discord_bot.fun")

MAGIC_8BALL_RESPONSES = [
    # Positive
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    # Neutral
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    # Negative
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]


class Fun(commands.Cog, name="Fun"):
    """Fun and entertainment commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── 8ball ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="The question you want to ask")
    async def eightball(self, interaction: discord.Interaction, question: str):
        response = random.choice(MAGIC_8BALL_RESPONSES)
        embed = discord.Embed(color=discord.Color.dark_purple())
        embed.add_field(name="🔮 Question", value=question, inline=False)
        embed.add_field(name="🎱 Answer", value=response, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── Roll ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="roll", description="Roll a dice (e.g. 2d6, 1d20)")
    @app_commands.describe(dice="Dice notation like 1d6, 2d20, 3d4 (max 10d100)")
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6"):
        try:
            parts = dice.lower().split("d")
            if len(parts) != 2:
                raise ValueError
            num, sides = int(parts[0]), int(parts[1])
            if not (1 <= num <= 10 and 2 <= sides <= 100):
                return await interaction.response.send_message(
                    "❌ Use between 1-10 dice with 2-100 sides each (e.g. `2d6`).", ephemeral=True
                )
            rolls = [random.randint(1, sides) for _ in range(num)]
            total = sum(rolls)
            rolls_str = ", ".join(str(r) for r in rolls)
            embed = discord.Embed(title="🎲 Dice Roll", color=discord.Color.blue())
            embed.add_field(name="Dice", value=dice.upper(), inline=True)
            if num > 1:
                embed.add_field(name="Rolls", value=rolls_str, inline=True)
            embed.add_field(name="Total", value=str(total), inline=True)
            await interaction.response.send_message(embed=embed)
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Invalid dice format. Use something like `2d6` or `1d20`.", ephemeral=True
            )

    # ── Coin flip ─────────────────────────────────────────────────────────────

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙" if result == "Heads" else "🪙"
        embed = discord.Embed(
            title=f"{emoji} Coin Flip",
            description=f"**{result}!**",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    # ── Poll ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="poll", description="Create a poll with up to 5 options")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        option5="Fifth option (optional)",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        option5: str = None,
    ):
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        options = [o for o in [option1, option2, option3, option4, option5] if o]

        embed = discord.Embed(
            title=f"📊 {question}",
            color=discord.Color.blurple(),
            description="\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options)),
        )
        embed.set_footer(text=f"Poll by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for i in range(len(options)):
            await message.add_reaction(number_emojis[i])

    # ── Random number ─────────────────────────────────────────────────────────

    @app_commands.command(name="random", description="Generate a random number")
    @app_commands.describe(
        minimum="Minimum value (default 1)",
        maximum="Maximum value (default 100)",
    )
    async def random_number(
        self,
        interaction: discord.Interaction,
        minimum: int = 1,
        maximum: int = 100,
    ):
        if minimum >= maximum:
            return await interaction.response.send_message(
                "❌ Minimum must be less than maximum.", ephemeral=True
            )
        result = random.randint(minimum, maximum)
        embed = discord.Embed(
            title="🎰 Random Number",
            description=f"**{result}**",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Range: {minimum}–{maximum}")
        await interaction.response.send_message(embed=embed)

    # ── Choose ────────────────────────────────────────────────────────────────

    @app_commands.command(name="choose", description="Choose between multiple options")
    @app_commands.describe(choices="Comma-separated list of choices (e.g. pizza, tacos, sushi)")
    async def choose(self, interaction: discord.Interaction, choices: str):
        options = [c.strip() for c in choices.split(",") if c.strip()]
        if len(options) < 2:
            return await interaction.response.send_message(
                "❌ Please provide at least 2 comma-separated choices.", ephemeral=True
            )
        picked = random.choice(options)
        embed = discord.Embed(
            title="🤔 I choose...",
            description=f"**{picked}**",
            color=discord.Color.teal(),
        )
        embed.add_field(name="Options", value=", ".join(options))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
