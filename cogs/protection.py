import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("discord_bot.protection")

# ── Per-guild settings (in-memory) ────────────────────────────────────────────
antiraid_settings: dict[int, dict] = {}
antispam_settings: dict[int, dict] = {}
antinuke_settings: dict[int, dict] = {}

join_tracker: dict[int, deque] = defaultdict(lambda: deque())
spam_tracker: dict[tuple, deque] = defaultdict(lambda: deque())
channel_delete_tracker: dict[tuple, deque] = defaultdict(lambda: deque())


def _antinuke(guild_id: int) -> dict:
    return antinuke_settings.setdefault(
        guild_id,
        {"enabled": False, "threshold": 2, "seconds": 10, "action": "ban", "log_channel": None},
    )


def _antiraid(guild_id: int) -> dict:
    return antiraid_settings.setdefault(
        guild_id,
        {"enabled": False, "threshold": 5, "seconds": 10, "action": "kick", "log_channel": None},
    )


def _antispam(guild_id: int) -> dict:
    return antispam_settings.setdefault(
        guild_id,
        {"enabled": False, "max_dupes": 3, "window": 10, "action": "timeout", "log_channel": None},
    )


class Protection(commands.Cog, name="Protection"):
    """Anti-raid, anti-spam, and anti-nuke protection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _log(self, guild: discord.Guild, log_channel_id: int | None, embed: discord.Embed):
        if log_channel_id:
            ch = guild.get_channel(log_channel_id)
            if ch:
                try:
                    await ch.send(embed=embed)
                except discord.Forbidden:
                    pass

    # ── Anti-nuke ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        cfg = _antinuke(guild.id)
        if not cfg["enabled"]:
            return

        now = datetime.now(timezone.utc)
        executor = None
        await asyncio.sleep(0.5)
        
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
                if abs((entry.created_at - now).total_seconds()) < 3:
                    executor = entry.user
                    break
        except discord.Forbidden:
            return

        if executor is None or executor.id == self.bot.user.id:
            return

        key = (guild.id, executor.id)
        tracker = channel_delete_tracker[key]
        tracker.append(now)

        cutoff = now - timedelta(seconds=cfg["seconds"])
        while tracker and tracker[0] < cutoff:
            tracker.popleft()

        if len(tracker) < cfg["threshold"]:
            return

        deleted_count = len(tracker)
        action = cfg["action"]
        action_taken = "No action (missing permissions)"
        member = guild.get_member(executor.id)

        try:
            if action == "ban":
                await guild.ban(executor, reason="[Anti-Nuke] Mass channel deletion")
                action_taken = "Banned"
            elif action == "kick" and member:
                await member.kick(reason="[Anti-Nuke] Mass channel deletion")
                action_taken = "Kicked"
            elif action == "strip" and member:
                roles_to_remove = [r for r in member.roles if r.managed is False and r != guild.default_role]
                await member.remove_roles(*roles_to_remove, reason="[Anti-Nuke] Mass channel deletion")
                action_taken = f"Stripped {len(roles_to_remove)} role(s)"
        except discord.Forbidden:
            action_taken = "Failed (missing permissions)"

        embed = discord.Embed(
            title="💣 Anti-Nuke Triggered",
            color=discord.Color.dark_red(),
            description=(
                f"**{executor}** (`{executor.id}`) deleted **{deleted_count}+ channels** "
                f"within **{cfg['seconds']}s**."
            ),
            timestamp=now,
        )
        embed.add_field(name="Action taken", value=action_taken)
        embed.add_field(name="Last channel deleted", value=f"#{channel.name}")
        embed.set_footer(text=f"Executor ID: {executor.id}")
        
        tracker.clear()  # Xóa tracker sau khi hoàn tất lấy thông tin
        await self._log(guild, cfg["log_channel"], embed)

    # ── Anti-raid ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = _antiraid(member.guild.id)
        if not cfg["enabled"]:
            return

        now = datetime.now(timezone.utc)
        tracker = join_tracker[member.guild.id]
        tracker.append(now)

        cutoff = now - timedelta(seconds=cfg["seconds"])
        while tracker and tracker[0] < cutoff:
            tracker.popleft()

        if len(tracker) >= cfg["threshold"]:
            recent_count = len(tracker)
            tracker.clear()

            recent = [
                m for m in member.guild.members
                if m.joined_at and m.joined_at >= cutoff and not m.bot
            ]

            action = cfg["action"]
            actioned = []
            for m in recent:
                try:
                    if action == "ban":
                        await m.ban(reason="[Anti-Raid] Automatic ban during raid")
                    else:
                        await m.kick(reason="[Anti-Raid] Automatic kick during raid")
                    actioned.append(str(m))
                except discord.Forbidden:
                    pass

            embed = discord.Embed(
                title="🚨 Raid Detected",
                color=discord.Color.red(),
                description=(
                    f"**{recent_count} members** joined within "
                    f"**{cfg['seconds']} seconds**.\n"
                    f"Action taken: **{action}** on {len(actioned)} member(s)."
                ),
                timestamp=now,
            )
            if actioned:
                embed.add_field(name="Members actioned", value="\n".join(actioned[:10]))

            await self._log(member.guild, cfg["log_channel"], embed)

    # ── Anti-spam ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        cfg = _antispam(message.guild.id)
        if not cfg["enabled"]:
            return

        content = message.content.strip()
        if len(content.split()) <= 4:
            return

        now = datetime.now(timezone.utc)
        key = (message.guild.id, message.author.id)
        history = spam_tracker[key]

        cutoff = now - timedelta(seconds=cfg["window"])
        while history and history[0][1] < cutoff:
            history.popleft()

        dupes = sum(1 for (text, _) in history if text == content)
        history.append((content, now))

        if dupes >= cfg["max_dupes"]:
            history.clear()

            try:
                await message.delete()
            except discord.Forbidden:
                pass

            member = message.author
            action_taken = "Message deleted"
            action = cfg["action"]

            try:
                if action == "timeout":
                    await member.timeout(timedelta(minutes=5), reason="[Anti-Spam] Duplicate message spam")
                    action_taken = "Message deleted + 5-minute timeout"
                elif action == "kick":
                    await member.kick(reason="[Anti-Spam] Duplicate message spam")
                    action_taken = "Message deleted + kicked"
            except discord.Forbidden:
                pass

            try:
                await message.channel.send(
                    f"⚠️ {member.mention} — duplicate spam detected. {action_taken}.",
                    delete_after=8,
                )
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="🔁 Spam Detected",
                color=discord.Color.orange(),
                description=f"**{member}** sent the same message {dupes + 1} time(s).",
                timestamp=now,
            )
            embed.add_field(name="Message", value=f"```{content[:200]}```", inline=False)
            embed.add_field(name="Action", value=action_taken)
            embed.add_field(name="Channel", value=message.channel.mention)
            await self._log(message.guild, cfg["log_channel"], embed)

    # ── Slash commands ───────────────────────────────────────────────────────

    antiraid_group = app_commands.Group(
        name="antiraid",
        description="Configure anti-raid protection",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @antiraid_group.command(name="on", description="Enable anti-raid protection")
    async def antiraid_on(self, interaction: discord.Interaction):
        cfg = _antiraid(interaction.guild.id)
        cfg["enabled"] = True
        embed = discord.Embed(
            title="🛡️ Anti-Raid Enabled",
            color=discord.Color.green(),
            description=(
                f"Will **{cfg['action']}** members if **{cfg['threshold']}+** "
                f"users join within **{cfg['seconds']}s**."
            ),
        )
        await interaction.response.send_message(embed=embed)

    @antiraid_group.command(name="off", description="Disable anti-raid protection")
    async def antiraid_off(self, interaction: discord.Interaction):
        cfg = _antiraid(interaction.guild.id)
        cfg["enabled"] = False
        await interaction.response.send_message("🔕 Anti-raid protection **disabled**.")

    @antiraid_group.command(name="status", description="Show current anti-raid settings")
    async def antiraid_status(self, interaction: discord.Interaction):
        cfg = _antiraid(interaction.guild.id)
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed = discord.Embed(
            title="🛡️ Anti-Raid Status",
            color=discord.Color.green() if cfg["enabled"] else discord.Color.red(),
        )
        embed.add_field(name="Status", value="✅ Enabled" if cfg["enabled"] else "❌ Disabled")
        embed.add_field(name="Trigger", value=f"{cfg['threshold']} joins / {cfg['seconds']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)

    @antiraid_group.command(name="config", description="Configure anti-raid thresholds and action")
    @app_commands.describe(
        threshold="Number of joins to trigger (default 5)",
        seconds="Time window in seconds (default 10)",
        action="Action to take on raiders",
        log_channel="Channel to log raid alerts",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Ban", value="ban"),
    ])
    async def antiraid_config(
        self,
        interaction: discord.Interaction,
        threshold: app_commands.Range[int, 2, 50] = None,
        seconds: app_commands.Range[int, 3, 60] = None,
        action: str = None,
        log_channel: discord.TextChannel = None,
    ):
        cfg = _antiraid(interaction.guild.id)
        if threshold is not None:
            cfg["threshold"] = threshold
        if seconds is not None:
            cfg["seconds"] = seconds
        if action is not None:
            cfg["action"] = action
        if log_channel is not None:
            cfg["log_channel"] = log_channel.id

        embed = discord.Embed(title="✅ Anti-Raid Config Updated", color=discord.Color.blurple())
        embed.add_field(name="Trigger", value=f"{cfg['threshold']} joins / {cfg['seconds']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)

    antispam_group = app_commands.Group(
        name="antispam",
        description="Configure anti-spam protection",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @antispam_group.command(name="on", description="Enable anti-spam protection")
    async def antispam_on(self, interaction: discord.Interaction):
        cfg = _antispam(interaction.guild.id)
        cfg["enabled"] = True
        embed = discord.Embed(
            title="🔁 Anti-Spam Enabled",
            color=discord.Color.green(),
            description=(
                f"Will **{cfg['action']}** members who send the same message "
                f"(5+ words) **{cfg['max_dupes']}+ times** within **{cfg['window']}s**."
            ),
        )
        await interaction.response.send_message(embed=embed)

    @antispam_group.command(name="off", description="Disable anti-spam protection")
    async def antispam_off(self, interaction: discord.Interaction):
        cfg = _antispam(interaction.guild.id)
        cfg["enabled"] = False
        await interaction.response.send_message("🔕 Anti-spam protection **disabled**.")

    @antispam_group.command(name="status", description="Show current anti-spam settings")
    async def antispam_status(self, interaction: discord.Interaction):
        cfg = _antispam(interaction.guild.id)
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed = discord.Embed(
            title="🔁 Anti-Spam Status",
            color=discord.Color.green() if cfg["enabled"] else discord.Color.red(),
        )
        embed.add_field(name="Status", value="✅ Enabled" if cfg["enabled"] else "❌ Disabled")
        embed.add_field(name="Max duplicates", value=str(cfg["max_dupes"]))
        embed.add_field(name="Window", value=f"{cfg['window']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)

    @antispam_group.command(name="config", description="Configure anti-spam thresholds and action")
    @app_commands.describe(
        max_dupes="How many duplicate sends before action (default 3)",
        window="Time window in seconds (default 10)",
        action="Action to take on spammers",
        log_channel="Channel to log spam alerts",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Delete only", value="delete"),
        app_commands.Choice(name="Delete + Timeout (5 min)", value="timeout"),
        app_commands.Choice(name="Delete + Kick", value="kick"),
    ])
    async def antispam_config(
        self,
        interaction: discord.Interaction,
        max_dupes: app_commands.Range[int, 2, 10] = None,
        window: app_commands.Range[int, 5, 60] = None,
        action: str = None,
        log_channel: discord.TextChannel = None,
    ):
        cfg = _antispam(interaction.guild.id)
        if max_dupes is not None:
            cfg["max_dupes"] = max_dupes
        if window is not None:
            cfg["window"] = window
        if action is not None:
            cfg["action"] = action
        if log_channel is not None:
            cfg["log_channel"] = log_channel.id

        embed = discord.Embed(title="✅ Anti-Spam Config Updated", color=discord.Color.blurple())
        embed.add_field(name="Max duplicates", value=str(cfg["max_dupes"]))
        embed.add_field(name="Window", value=f"{cfg['window']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)

    antinuke_group = app_commands.Group(
        name="antinuke",
        description="Configure anti-nuke protection",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @antinuke_group.command(name="on", description="Enable anti-nuke protection")
    async def antinuke_on(self, interaction: discord.Interaction):
        cfg = _antinuke(interaction.guild.id)
        cfg["enabled"] = True
        embed = discord.Embed(
            title="💣 Anti-Nuke Enabled",
            color=discord.Color.green(),
            description=(
                f"Will **{cfg['action']}** any user/bot that deletes "
                f"**{cfg['threshold']}+** channels within **{cfg['seconds']}s**."
            ),
        )
        await interaction.response.send_message(embed=embed)

    @antinuke_group.command(name="off", description="Disable anti-nuke protection")
    async def antinuke_off(self, interaction: discord.Interaction):
        cfg = _antinuke(interaction.guild.id)
        cfg["enabled"] = False
        await interaction.response.send_message("🔕 Anti-nuke protection **disabled**.")

    @antinuke_group.command(name="status", description="Show current anti-nuke settings")
    async def antinuke_status(self, interaction: discord.Interaction):
        cfg = _antinuke(interaction.guild.id)
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed = discord.Embed(
            title="💣 Anti-Nuke Status",
            color=discord.Color.green() if cfg["enabled"] else discord.Color.red(),
        )
        embed.add_field(name="Status", value="✅ Enabled" if cfg["enabled"] else "❌ Disabled")
        embed.add_field(name="Trigger", value=f"{cfg['threshold']} deletions / {cfg['seconds']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)

    @antinuke_group.command(name="config", description="Configure anti-nuke thresholds and action")
    @app_commands.describe(
        threshold="Number of channel deletions to trigger (default 2)",
        seconds="Time window in seconds (default 10)",
        action="Action to take on the offender",
        log_channel="Channel to log nuke alerts",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Ban", value="ban"),
        app_commands.Choice(name="Kick", value="kick"),
        app_commands.Choice(name="Strip all roles", value="strip"),
    ])
    async def antinuke_config(
        self,
        interaction: discord.Interaction,
        threshold: app_commands.Range[int, 1, 20] = None,
        seconds: app_commands.Range[int, 3, 60] = None,
        action: str = None,
        log_channel: discord.TextChannel = None,
    ):
        cfg = _antinuke(interaction.guild.id)
        if threshold is not None:
            cfg["threshold"] = threshold
        if seconds is not None:
            cfg["seconds"] = seconds
        if action is not None:
            cfg["action"] = action
        if log_channel is not None:
            cfg["log_channel"] = log_channel.id

        embed = discord.Embed(title="✅ Anti-Nuke Config Updated", color=discord.Color.blurple())
        embed.add_field(name="Trigger", value=f"{cfg['threshold']} deletions / {cfg['seconds']}s")
        embed.add_field(name="Action", value=cfg["action"].capitalize())
        log_ch = interaction.guild.get_channel(cfg["log_channel"]) if cfg["log_channel"] else None
        embed.add_field(name="Log Channel", value=log_ch.mention if log_ch else "Not set")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    cog = Protection(bot)
    bot.add_listener(cog.on_member_join)
    bot.add_listener(cog.on_message)
    bot.add_listener(cog.on_guild_channel_delete)
    await bot.add_cog(cog)
