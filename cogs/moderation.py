import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger("discord_bot.moderation")


class Moderation(commands.Cog, name="Moderation"):
    """Server moderation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Kick ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ You can't kick yourself.", ephemeral=True)
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You can't kick someone with an equal or higher role.", ephemeral=True
            )
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.orange(),
                description=f"**{member}** has been kicked.",
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} kicked {member} in {interaction.guild}: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick that member.", ephemeral=True)

    # ── Ban ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban",
        delete_days="Days of messages to delete (0-7)",
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ You can't ban yourself.", ephemeral=True)
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You can't ban someone with an equal or higher role.", ephemeral=True
            )
        try:
            await member.ban(reason=reason, delete_message_days=delete_days)
            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.red(),
                description=f"**{member}** has been banned.",
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
            logger.info(f"{interaction.user} banned {member} in {interaction.guild}: {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban that member.", ephemeral=True)

    # ── Unban ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="unban", description="Unban a user by their ID")
    @app_commands.describe(user_id="The user ID to unban", reason="Reason for the unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "No reason provided",
    ):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            embed = discord.Embed(
                title="✅ User Unbanned",
                color=discord.Color.green(),
                description=f"**{user}** has been unbanned.",
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)

    # ── Timeout ───────────────────────────────────────────────────────────────

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(
        member="The member to timeout",
        minutes="Duration in minutes (1-40320)",
        reason="Reason for the timeout",
    )
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "No reason provided",
    ):
        import datetime

        if member == interaction.user:
            return await interaction.response.send_message("❌ You can't timeout yourself.", ephemeral=True)
        try:
            duration = datetime.timedelta(minutes=minutes)
            await member.timeout(duration, reason=reason)
            embed = discord.Embed(
                title="⏱️ Member Timed Out",
                color=discord.Color.yellow(),
                description=f"**{member}** has been timed out for **{minutes} minute(s)**.",
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout that member.", ephemeral=True)

    # ── Purge ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="purge", description="Bulk delete messages in a channel")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        member="Only delete messages from this member (optional)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        member: discord.Member = None,
    ):
        await interaction.response.defer(ephemeral=True)

        def check(msg):
            return member is None or msg.author == member

        deleted = await interaction.channel.purge(limit=amount, check=check)
        target = f" from **{member}**" if member else ""
        await interaction.followup.send(
            f"🗑️ Deleted **{len(deleted)}** message(s){target}.", ephemeral=True
        )

    # ── Warn ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="The member to warn", reason="Reason for the warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ You can't warn yourself.", ephemeral=True)

        embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.gold(),
            description=f"**{member.mention}** has been warned.",
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        await interaction.response.send_message(embed=embed)

        # DM the warned user
        try:
            dm_embed = discord.Embed(
                title="⚠️ You have been warned",
                color=discord.Color.gold(),
                description=f"You were warned in **{interaction.guild.name}**.",
            )
            dm_embed.add_field(name="Reason", value=reason)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # User has DMs disabled


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
      
