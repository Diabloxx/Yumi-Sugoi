"""
commands.py - Central place for all new / (slash) and ! (prefix) commands for Yumi Sugoi.

- Import this module in main.py to register new commands.
- Add new commands here for easy management and future expansion.
- Supports both @bot.command (prefix) and @bot.tree.command (slash) commands.
"""

import discord
from discord.ext import commands
from discord import app_commands

# Example: Add your bot instance here if needed
# from .main import bot

# Example prefix command (!hello)
def setup_prefix_commands(bot):

    @bot.command(name="userinfo")
    async def userinfo(ctx, member: discord.Member = None):
        """Show info about yourself or another user."""
        member = member or ctx.author
        embed = discord.Embed(title=f"User Info: {member.display_name}", color=discord.Color.blue())
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined", value=member.joined_at.strftime('%Y-%m-%d'))
        embed.add_field(name="Account Created", value=member.created_at.strftime('%Y-%m-%d'))
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @bot.command(name="serverinfo")
    async def serverinfo(ctx):
        """Show info about the server."""
        guild = ctx.guild
        embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.green())
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Owner", value=guild.owner.display_name)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=guild.created_at.strftime('%Y-%m-%d'))
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        await ctx.send(embed=embed)

    @bot.command(name="ping")
    async def ping(ctx):
        """Check bot latency."""
        latency = round(bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency}ms")

    @bot.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(ctx, count: int):
        """Delete the last N messages in this channel (admin only)."""
        await ctx.channel.purge(limit=count+1)
        await ctx.send(f"🧹 Deleted the last {count} messages.", delete_after=5)

    @bot.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(ctx, member: discord.Member, *, reason: str = None):
        """Kick a user from the server."""
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.display_name} was kicked. Reason: {reason or 'No reason provided.'}")

    @bot.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(ctx, member: discord.Member, *, reason: str = None):
        """Ban a user from the server."""
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.display_name} was banned. Reason: {reason or 'No reason provided.'}")

    @bot.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(ctx, user: str):
        """Unban a user by name#discriminator or user ID."""
        bans = await ctx.guild.bans()
        for ban_entry in bans:
            banned_user = ban_entry.user
            if user == str(banned_user) or user == str(banned_user.id):
                await ctx.guild.unban(banned_user)
                await ctx.send(f"✅ Unbanned {banned_user.display_name}.")
                return
        await ctx.send("User not found in ban list.")

    # --- Moderation: Slowmode ---
    @bot.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(ctx, seconds: int):
        """Set slowmode for the current channel (in seconds)."""
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"🐢 Slowmode set to {seconds} seconds.")

    # --- Moderation: Warn, Warnings, Clearwarnings ---
    import json
    import os
    WARNINGS_FILE = os.path.join(os.path.dirname(__file__), '../datasets/warnings.json')
    def load_warnings():
        try:
            with open(WARNINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    def save_warnings(warnings):
        with open(WARNINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(warnings, f, ensure_ascii=False, indent=2)
    
    @bot.command(name="warn")
    @commands.has_permissions(manage_messages=True)
    async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Warn a user (logs warning)."""
        warnings = load_warnings()
        user_id = str(member.id)
        warnings.setdefault(user_id, []).append({
            "moderator": str(ctx.author),
            "reason": reason,
            "timestamp": str(ctx.message.created_at)
        })
        save_warnings(warnings)
        await ctx.send(f"⚠️ {member.display_name} has been warned. Reason: {reason}")

    @bot.command(name="warnings")
    async def warnings_cmd(ctx, member: discord.Member = None):
        """List warnings for a user."""
        member = member or ctx.author
        warnings = load_warnings()
        user_id = str(member.id)
        user_warnings = warnings.get(user_id, [])
        if not user_warnings:
            await ctx.send(f"✅ {member.display_name} has no warnings.")
            return
        msg = f"Warnings for {member.display_name}:\n"
        for i, w in enumerate(user_warnings, 1):
            msg += f"{i}. By {w['moderator']} at {w['timestamp']}: {w['reason']}\n"
        await ctx.send(msg)

    @bot.command(name="clearwarnings")
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(ctx, member: discord.Member = None):
        """Clear all warnings for a user."""
        member = member or ctx.author
        warnings = load_warnings()
        user_id = str(member.id)
        if user_id in warnings:
            del warnings[user_id]
            save_warnings(warnings)
            await ctx.send(f"✅ Cleared all warnings for {member.display_name}.")
        else:
            await ctx.send(f"{member.display_name} has no warnings to clear.")

    @bot.command(name="restartbot")
    async def restartbot(ctx):
        """Restart the bot process (owner only)."""
        if getattr(ctx.author, 'id', None) != 594793428634566666:
            await ctx.send("You are not authorized to restart the bot.")
            return
        await ctx.send("🔄 Restarting Yumi Sugoi... Please wait.")
        import sys, os
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # --- Slash versions ---
    @bot.tree.command(name="userinfo", description="Show info about yourself or another user.")
    @discord.app_commands.describe(member="The user to get info about")
    async def userinfo_slash(interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"User Info: {member.display_name}", color=discord.Color.blue())
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined", value=member.joined_at.strftime('%Y-%m-%d'))
        embed.add_field(name="Account Created", value=member.created_at.strftime('%Y-%m-%d'))
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="serverinfo", description="Show info about the server.")
    async def serverinfo_slash(interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.green())
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Owner", value=guild.owner.display_name)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=guild.created_at.strftime('%Y-%m-%d'))
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="ping", description="Check bot latency.")
    async def ping_slash(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency}ms")

    @bot.tree.command(name="purge", description="Delete the last N messages in this channel (admin only).")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(count="Number of messages to delete")
    async def purge_slash(interaction: discord.Interaction, count: int):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=count+1)
        await interaction.followup.send(f"🧹 Deleted the last {count} messages.", ephemeral=True)

    @bot.tree.command(name="kick", description="Kick a user from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="User to kick", reason="Reason for kick")
    async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member.display_name} was kicked. Reason: {reason or 'No reason provided.'}", ephemeral=True)

    @bot.tree.command(name="ban", description="Ban a user from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(member="User to ban", reason="Reason for ban")
    async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = None):
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member.display_name} was banned. Reason: {reason or 'No reason provided.'}", ephemeral=True)

    @bot.tree.command(name="unban", description="Unban a user by name#discriminator or user ID.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user="User to unban (name#discriminator or ID)")
    async def unban_slash(interaction: discord.Interaction, user: str):
        bans = await interaction.guild.bans()
        for ban_entry in bans:
            banned_user = ban_entry.user
            if user == str(banned_user) or user == str(banned_user.id):
                await interaction.guild.unban(banned_user)
                await interaction.response.send_message(f"✅ Unbanned {banned_user.display_name}.", ephemeral=True)
                return
        await interaction.response.send_message("User not found in ban list.", ephemeral=True)

    @bot.tree.command(name="slowmode", description="Set slowmode for the current channel (in seconds).")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(seconds="Slowmode delay in seconds")
    async def slowmode_slash(interaction: discord.Interaction, seconds: int):
        await interaction.channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message(f"🐢 Slowmode set to {seconds} seconds.", ephemeral=True)

    @bot.tree.command(name="warn", description="Warn a user (logs warning).")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(member="User to warn", reason="Reason for warning")
    async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided."):
        warnings = load_warnings()
        user_id = str(member.id)
        warnings.setdefault(user_id, []).append({
            "moderator": str(interaction.user),
            "reason": reason,
            "timestamp": str(interaction.created_at)
        })
        save_warnings(warnings)
        await interaction.response.send_message(f"⚠️ {member.display_name} has been warned. Reason: {reason}", ephemeral=True)

    @bot.tree.command(name="warnings", description="List warnings for a user.")
    @app_commands.describe(member="User to check warnings for")
    async def warnings_slash(interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        warnings = load_warnings()
        user_id = str(member.id)
        user_warnings = warnings.get(user_id, [])
        if not user_warnings:
            await interaction.response.send_message(f"✅ {member.display_name} has no warnings.", ephemeral=True)
            return
        msg = f"Warnings for {member.display_name}:\n"
        for i, w in enumerate(user_warnings, 1):
            msg += f"{i}. By {w['moderator']} at {w['timestamp']}: {w['reason']}\n"
        await interaction.response.send_message(msg, ephemeral=True)

    @bot.tree.command(name="clearwarnings", description="Clear all warnings for a user.")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(member="User to clear warnings for")
    async def clearwarnings_slash(interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        warnings = load_warnings()
        user_id = str(member.id)
        if user_id in warnings:
            del warnings[user_id]
            save_warnings(warnings)
            await interaction.response.send_message(f"✅ Cleared all warnings for {member.display_name}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{member.display_name} has no warnings to clear.", ephemeral=True)
