import os
import random
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ------------- ENV SETUP -------------

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN missing hai! Render / .env me set karo.")


# ------------- INTENTS -------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# ------------- CUSTOM BOT CLASS -------------

class XtremeBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        # default help command disable
        kwargs["help_command"] = None
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # slash commands sync
        try:
            await self.tree.sync()
            print("Slash commands synced ✅")
        except Exception as e:
            print("Slash sync error:", e)


bot = XtremeBot(command_prefix="!", intents=intents)


# ------------- WARN STORAGE (IN-MEMORY) -------------

# warnings_store[guild_id][user_id] = count
warnings_store = {}

# ------------- TIMEOUT DURATIONS -------------

TIMEOUT_PRESET = {
    "10s": timedelta(seconds=10),
    "1m": timedelta(minutes=1),
    "10m": timedelta(minutes=10),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
}


# ------------- UTILITY HELPERS -------------

def get_warn_count(guild_id: int, user_id: int) -> int:
    return warnings_store.get(guild_id, {}).get(user_id, 0)


def add_warn(guild_id: int, user_id: int) -> int:
    if guild_id not in warnings_store:
        warnings_store[guild_id] = {}
    warnings_store[guild_id][user_id] = warnings_store[guild_id].get(user_id, 0) + 1
    return warnings_store[guild_id][user_id]


def remove_warns(guild_id: int, user_id: int) -> None:
    if guild_id in warnings_store and user_id in warnings_store[guild_id]:
        del warnings_store[guild_id][user_id]


async def can_act_on(
    interaction_or_ctx,
    moderator: discord.Member,
    target: discord.Member,
) -> bool:
    """
    Role hierarchy + self/bot protection
    interaction_or_ctx -> ctx ya interaction
    """
    # can't act on self
    if target.id == moderator.id:
        msg = "Apne aap pe action nahi le sakte 😅"
        if isinstance(interaction_or_ctx, discord.Interaction):
            await interaction_or_ctx.response.send_message(msg, ephemeral=True)
        else:
            await interaction_or_ctx.send(msg)
        return False

    # can't act on bot
    if target.bot:
        msg = "Bot pe aise action nahi le sakte 😐"
        if isinstance(interaction_or_ctx, discord.Interaction):
            await interaction_or_ctx.response.send_message(msg, ephemeral=True)
        else:
            await interaction_or_ctx.send(msg)
        return False

    guild = target.guild
    bot_member = guild.me

    # moderator role check
    if moderator.top_role <= target.top_role and guild.owner_id != moderator.id:
        msg = "Unke role tumse upar ya barabar hai 😶 Action allowed nahi."
        if isinstance(interaction_or_ctx, discord.Interaction):
            await interaction_or_ctx.response.send_message(msg, ephemeral=True)
        else:
            await interaction_or_ctx.send(msg)
        return False

    # bot role check
    if bot_member.top_role <= target.top_role:
        msg = "Mera role unse niche hai 😭 mujhe upar role do phir try karo."
        if isinstance(interaction_or_ctx, discord.Interaction):
            await interaction_or_ctx.response.send_message(msg, ephemeral=True)
        else:
            await interaction_or_ctx.send(msg)
        return False

    return True


async def do_timeout(
    interaction_or_ctx,
    target: discord.Member,
    delta: timedelta,
    reason: str,
):
    guild = target.guild

    if isinstance(interaction_or_ctx, discord.Interaction):
        moderator = interaction_or_ctx.user
    else:
        moderator = interaction_or_ctx.author

    if not await can_act_on(interaction_or_ctx, moderator, target):
        return

    until = discord.utils.utcnow() + delta
    await target.timeout(until=until, reason=reason)

    msg = (
        f"⏳ {target.mention} ko `{delta}` ke liye timeout diya gaya.\n"
        f"Reason: **{reason}**"
    )

    if isinstance(interaction_or_ctx, discord.Interaction):
        await interaction_or_ctx.response.send_message(msg)
    else:
        await interaction_or_ctx.send(msg)


# ------------- EVENTS -------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Xtreme bot online ⚡")


# ------------- MODERATION: KICK -------------

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason"):
    if not await can_act_on(ctx, ctx.author, member):
        return

    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} ko kick kar diya gaya. Reason: **{reason}**")


@kick_prefix.error
async def kick_prefix_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Tumhare paas kick permission nahi hai 😶")


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    if not await can_act_on(interaction, interaction.user, member):
        return

    await member.kick(reason=reason)
    await interaction.response.send_message(
        f"👢 {member.mention} ko kick kar diya gaya. Reason: **{reason}**"
    )


# ------------- MODERATION: BAN / UNBAN -------------

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_prefix(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason"):
    if not await can_act_on(ctx, ctx.author, member):
        return

    await member.ban(reason=reason, delete_message_days=0)
    await ctx.send(f"🔨 {member.mention} ko ban kar diya gaya. Reason: **{reason}**")


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    if not await await can_act_on(interaction, interaction.user, member):
        return

    await member.ban(reason=reason, delete_message_days=0)
    await interaction.response.send_message(
        f"🔨 {member.mention} ko ban kar diya gaya. Reason: **{reason}**"
    )


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_prefix(ctx: commands.Context, *, user: discord.User):
    await ctx.guild.unban(user)
    await ctx.send(f"✅ {user.mention} ka ban hata diya gaya.")


@bot.tree.command(name="unban", description="Unban a user (ID or mention)")
@app_commands.checks.has_permissions(ban_members=True)
async def unban_slash(interaction: discord.Interaction, user: discord.User):
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"✅ {user.mention} ka ban hata diya gaya.")


# ------------- MODERATION: TIMEOUT -------------

# prefix: !timeout @user 10m reason
@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_prefix(
    ctx: commands.Context,
    member: discord.Member,
    duration: str,
    *,
    reason: str = "No reason",
):
    duration = duration.lower()
    if duration not in TIMEOUT_PRESET:
        valid = ", ".join(TIMEOUT_PRESET.keys())
        await ctx.send(f"❌ Duration galat hai. Use: {valid}")
        return

    delta = TIMEOUT_PRESET[duration]
    await do_timeout(ctx, member, delta, reason)


# slash: /timeout member duration reason
TIMEOUT_CHOICES = [
    app_commands.Choice(name="10 seconds", value="10s"),
    app_commands.Choice(name="1 minute", value="1m"),
    app_commands.Choice(name="10 minutes", value="10m"),
    app_commands.Choice(name="1 hour", value="1h"),
    app_commands.Choice(name="2 hours", value="2h"),
]


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(
    member="Kisko timeout karna hai?",
    duration="Kitne time ke liye?",
    reason="Reason (optional)",
)
@app_commands.choices(duration=TIMEOUT_CHOICES)
async def timeout_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: app_commands.Choice[str],
    reason: str = "No reason",
):
    key = duration.value
    delta = TIMEOUT_PRESET.get(key)
    if not delta:
        await interaction.response.send_message("❌ Duration galat hai.", ephemeral=True)
        return

    await do_timeout(interaction, member, delta, reason)


# ------------- WARN + AUTO TIMEOUT -------------

AUTO_TIMEOUT_AFTER = 3  # 3 warns ke baad auto timeout 10m


async def send_warn_dm(member: discord.Member, guild_name: str, reason: str, count: int):
    try:
        await member.send(
            f"⚠️ Tumhe **{guild_name}** me warn mila hai.\n"
            f"Reason: **{reason}**\n"
            f"Total warns: **{count}**"
        )
    except Exception:
        # DMs closed etc
        pass


@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_prefix(
    ctx: commands.Context,
    member: discord.Member,
    *,
    reason: str = "No reason",
):
    if not await can_act_on(ctx, ctx.author, member):
        return

    count = add_warn(ctx.guild.id, member.id)
    await send_warn_dm(member, ctx.guild.name, reason, count)

    msg = (
        f"⚠️ {member.mention} ko warn diya gaya. Reason: **{reason}**\n"
        f"Total warns: **{count}**"
    )

    # auto-timeout
    if count >= AUTO_TIMEOUT_AFTER:
        delta = TIMEOUT_PRESET["10m"]
        await member.timeout(
            until=discord.utils.utcnow() + delta,
            reason=f"Auto-timeout after {count} warns. Last reason: {reason}",
        )
        msg += "\n⏳ 3 warns complete → auto 10 minute timeout laga diya gaya."
        remove_warns(ctx.guild.id, member.id)

    await ctx.send(msg)


@bot.tree.command(name="warn", description="Warn a member (auto timeout after 3)")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason",
):
    if not await can_act_on(interaction, interaction.user, member):
        return

    guild = interaction.guild
    count = add_warn(guild.id, member.id)
    await send_warn_dm(member, guild.name, reason, count)

    msg = (
        f"⚠️ {member.mention} ko warn diya gaya. Reason: **{reason}**\n"
        f"Total warns: **{count}**"
    )

    if count >= AUTO_TIMEOUT_AFTER:
        delta = TIMEOUT_PRESET["10m"]
        await member.timeout(
            until=discord.utils.utcnow() + delta,
            reason=f"Auto-timeout after {count} warns. Last reason: {reason}",
        )
        msg += "\n⏳ 3 warns complete → auto 10 minute timeout laga diya gaya."
        remove_warns(guild.id, member.id)

    await interaction.response.send_message(msg)


# ------------- COINFLIP -------------

@bot.command(name="coinflip")
async def coinflip_prefix(ctx: commands.Context):
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 Coin flip: **{result}**")


@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip_slash(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    await interaction.response.send_message(f"🪙 Coin flip: **{result}**")


# ------------- HELP -------------

HELP_TEXT = """
**Xtreme Bot – Commands**

**Prefix** (default: `!`)
> `!help` – ye help menu
> `!kick @user [reason]`
> `!ban @user [reason]`
> `!unban userID`
> `!timeout @user <10s|1m|10m|1h|2h> [reason]`
> `!warn @user [reason]` (3 warns → auto 10m timeout)
> `!coinflip`

**Slash**
> `/help`
> `/kick`
> `/ban`
> `/unban`
> `/timeout`
> `/warn`
> `/coinflip`
""".strip()


@bot.command(name="help")
async def help_prefix(ctx: commands.Context):
    await ctx.send(HELP_TEXT)


@bot.tree.command(name="help", description="Show Xtreme help menu")
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_TEXT, ephemeral=True)


# ------------- RUN BOT -------------

bot.run(DISCORD_BOT_TOKEN)
