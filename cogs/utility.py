import discord
from discord import app_commands
from discord.ext import commands
import time
import logging

logger = logging.getLogger("discord_bot.utility")


class Utility(commands.Cog, name="Utility"):
    """Utility and information commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Ping ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = (
            discord.Color.green() if latency < 100
            else discord.Color.yellow() if latency < 200
            else discord.Color.red()
        )
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="WebSocket Latency", value=f"`{latency}ms`")
        await interaction.response.send_message(embed=embed)

    # ── Server info ───────────────────────────────────────────────────────────

    @app_commands.command(name="serverinfo", description="Show information about this server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=guild.name,
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(guild.created_at, style="R"),
            inline=False,
        )
        embed.set_footer(text=f"Server ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

    # ── User info ─────────────────────────────────────────────────────────────

    @app_commands.command(name="userinfo", description="Show information about a user")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]

        embed = discord.Embed(
            title=str(member),
            color=member.color if member.color != discord.Color.default() else discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(member.created_at, style="R"),
            inline=True,
        )
        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Unknown",
            inline=True,
        )
        if roles:
            embed.add_field(
                name=f"Roles ({len(roles)})",
                value=" ".join(roles[:10]) + (" ..." if len(roles) > 10 else ""),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    # ── Avatar ────────────────────────────────────────────────────────────────

    @app_commands.command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(member="The member whose avatar to show (defaults to yourself)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(name="Download", value=f"[PNG]({member.display_avatar.replace(format='png').url}) | [JPG]({member.display_avatar.replace(format='jpg').url})")
        await interaction.response.send_message(embed=embed)

    # ── Invite ────────────────────────────────────────────────────────────────

    @app_commands.command(name="invite", description="Get the invite link for this server")
    async def invite(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📨 Invite Link",
            description="[Click here to invite others to the server!](https://discord.gg/yY9z43PQ37)",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Link", value="https://discord.gg/yY9z43PQ37")
        await interaction.response.send_message(embed=embed)

    # ── Say ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="say", description="Make the bot send a message")
    @app_commands.describe(
        message="The message to send",
        channel="Channel to send the message in (defaults to current channel)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None,
    ):
        target = channel or interaction.channel
        await target.send(message)
        if channel and channel != interaction.channel:
            await interaction.response.send_message(
                f"✅ Message sent in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message("✅ Message sent.", ephemeral=True)

    # ── Say Embed ─────────────────────────────────────────────────────────────

    @app_commands.command(name="sayembed", description="Make the bot send a formatted embed message")
    @app_commands.describe(
        title="Title of the embed",
        description="Body text of the embed",
        color="Hex color code (e.g. ff5733). Defaults to blurple",
        channel="Channel to send the embed in (defaults to current channel)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def sayembed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: str = None,
        channel: discord.TextChannel = None,
    ):
        target = channel or interaction.channel

        embed_color = discord.Color.blurple()
        if color:
            try:
                embed_color = discord.Color(int(color.lstrip("#"), 16))
            except ValueError:
                return await interaction.response.send_message(
                    "❌ Invalid color. Use a hex code like `ff5733`.", ephemeral=True
                )

        embed = discord.Embed(title=title, description=description, color=embed_color)
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        await target.send(embed=embed)

        if channel and channel != interaction.channel:
            await interaction.response.send_message(
                f"✅ Embed sent in {channel.mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message("✅ Embed sent.", ephemeral=True)

    # ── DM ────────────────────────────────────────────────────────────────────

    @app_commands.command(name="saydm", description="Send a DM to a member as the bot")
    @app_commands.describe(
        member="The member to DM",
        message="The message to send",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def saydm(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str,
    ):
        try:
            await member.send(message)
            await interaction.response.send_message(
                f"✅ DM sent to **{member.display_name}**.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Could not DM **{member.display_name}** — they may have DMs disabled.",
                ephemeral=True,
            )

    # ── Edit Message ──────────────────────────────────────────────────────────

    @app_commands.command(name="editmessage", description="Edit a message the bot previously sent")
    @app_commands.describe(
        message_id="ID of the bot message to edit",
        new_content="The new message content",
        channel="Channel where the message is (defaults to current channel)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def editmessage(
        self,
        interaction: discord.Interaction,
        message_id: str,
        new_content: str,
        channel: discord.TextChannel = None,
    ):
        target = channel or interaction.channel
        try:
            msg = await target.fetch_message(int(message_id))
            if msg.author != self.bot.user:
                return await interaction.response.send_message(
                    "❌ I can only edit my own messages.", ephemeral=True
                )
            await msg.edit(content=new_content)
            await interaction.response.send_message("✅ Message updated.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ Message not found. Make sure the ID is correct and the channel is right.",
                ephemeral=True,
            )
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

    # ── Help ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show all available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Bot Commands",
            description="All commands are available as slash commands — type `/` to see them.",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "`/kick` — Kick a member\n"
                "`/ban` — Ban a member\n"
                "`/unban` — Unban by user ID\n"
                "`/timeout` — Timeout a member\n"
                "`/purge` — Bulk delete messages\n"
                "`/warn` — Warn a member"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎉 Fun",
            value=(
                "`/8ball` — Ask the magic 8-ball\n"
                "`/roll` — Roll dice (e.g. 2d6)\n"
                "`/coinflip` — Flip a coin\n"
                "`/poll` — Create a poll\n"
                "`/random` — Random number\n"
                "`/choose` — Pick from options"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Protection",
            value=(
                "`/antiraid on/off` — Enable/disable anti-raid\n"
                "`/antiraid config` — Set trigger threshold & action\n"
                "`/antiraid status` — Show anti-raid settings\n"
                "`/antispam on/off` — Enable/disable anti-spam\n"
                "`/antispam config` — Set duplicate limit & action\n"
                "`/antispam status` — Show anti-spam settings\n"
                "`/antinuke on/off` — Enable/disable anti-nuke\n"
                "`/antinuke config` — Set deletion threshold & action\n"
                "`/antinuke status` — Show anti-nuke settings"
            ),
            inline=False,
        )
        embed.add_field(
            name="📢 Say",
            value=(
                "`/say` — Bot sends a plain message\n"
                "`/sayembed` — Bot sends a formatted embed\n"
                "`/saydm` — Bot DMs a member\n"
                "`/editmessage` — Edit a bot message by ID"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔧 Utility",
            value=(
                "`/invite` — Get the server invite link\n"
                "`/ping` — Check bot latency\n"
                "`/serverinfo` — Server details\n"
                "`/userinfo` — User details\n"
                "`/avatar` — Show a user's avatar\n"
                "`/help` — This message"
            ),
            inline=False,
        )
        embed.set_footer(text="Moderation commands require the appropriate permissions.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
